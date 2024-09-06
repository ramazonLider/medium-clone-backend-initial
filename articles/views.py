from rest_framework import status, viewsets, generics
from rest_framework.response import Response
from django_redis import get_redis_connection
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from .models import Article, TopicFollow, Topic, Comment, Favorite
from rest_framework.exceptions import NotFound, PermissionDenied
from .filters import ArticleFilter
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from .serializers import ArticleSerializer, CommentSerializer, ArticleDetailCommentsSerializer
class ArticlesView(viewsets.ModelViewSet):
    queryset = Article.objects.filter(status__iexact="publish")
    serializer_class = ArticleSerializer
    http_method_names = ['get', 'post', 'patch', 'delete'] # method nomlari
    permission_classes = [IsAuthenticated] # permissionlar
    filter_backends = [DjangoFilterBackend] # filters qo'shish uchun ishlatildi
    filterset_class = ArticleFilter # filtersdan chaqirish kerak
    search_fields = ['title', 'summary', 'content', 'topics__name']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ArticleSerializer
        return ArticleSerializer

    def create(self, request, *args, **kwargs):
        author = request.user
        if not author.is_authenticated:
            return Response({'error': 'Xato mavjud'}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data.copy()
        data['author'] = author.id # authorni aniqlash

        serializer = self.get_serializer(data=data) # ma'lumot kiritish
        if serializer.is_valid():
            self.perform_create(serializer) # ma'lumot yaratish
            response_data = serializer.data
            headers = self.get_success_headers(response_data)

            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
        else:
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def patch(self, request, *args, **kwargs):
        redis_conn = get_redis_connection('default')
        redis_conn.set('test_key', 'test_value', ex=3600)
        cached_value = redis_conn.get('test_key')
        print(cached_value)
        response = super().partial_update(request, *args, **kwargs)
        print(response.data)
        return Response(response.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        article = self.get_object()
        article.status = "trash"
        article.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class TopicFollowView(viewsets.ViewSet):
    def create(self, request, topic_id=None):
        user = request.user
        try:
            topic = Topic.objects.get(id=topic_id)
        except Topic.DoesNotExist:
            return Response({"detail": "Hech qanday mavzu berilgan soʻrovga mos kelmaydi."}, status=status.HTTP_404_NOT_FOUND)

        if TopicFollow.objects.filter(user=user, topic=topic).exists():
            return Response({"detail": f"Siz allaqachon '{topic.name}' mavzusini kuzatyapsiz."}, status=status.HTTP_200_OK)

        TopicFollow.objects.create(user=user, topic=topic)
        return Response({"detail": f"Siz '{topic.name}' mavzusini kuzatyapsiz."}, status=status.HTTP_201_CREATED)

    def destroy(self, request, topic_id=None):
        user = request.user
        try:
            topic = Topic.objects.get(id=topic_id)
        except Topic.DoesNotExist:
            return Response({"detail": "Hech qanday mavzu berilgan soʻrovga mos kelmaydi."}, status=status.HTTP_404_NOT_FOUND)

        follow = TopicFollow.objects.filter(user=user, topic=topic).first()
        if not follow:
            return Response({"detail": f"Siz '{topic.name}' mavzusini kuzatmaysiz."}, status=status.HTTP_404_NOT_FOUND)

        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class CreateCommentsView(generics.CreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        article_id = self.kwargs.get('article_id')
        article = get_object_or_404(Article, pk=article_id)

        if article.status != 'publish':
            raise NotFound("This article is inactive and cannot accept comments.")

        # Save the serializer with user and article
        serializer.save(user=self.request.user, article=article)

class CommentsView(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def partial_update(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to perform this action.")
        return super().destroy(request, *args, **kwargs)

class ArticleDetailCommentsView(generics.ListAPIView):
    serializer_class = ArticleDetailCommentsSerializer

    def get_queryset(self):
        article_id = self.kwargs.get('article_id')
        return Article.objects.filter(pk=article_id).prefetch_related('article_comments')

class FavoriteArticleView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        article_id = self.kwargs.get('id')
        article = Article.objects.filter(id=article_id).first()

        if not article:
            raise NotFound(detail="Maqola topilmadi.")

        favorite, created = Favorite.objects.get_or_create(user=request.user, article=article)

        if created:
            return Response({"detail": "Maqola sevimlilarga qo'shildi."}, status=status.HTTP_201_CREATED)
        else:
            return Response({"detail": "Maqola sevimlilarga allaqachon qo'shilgan."}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, *args, **kwargs):
        article_id = self.kwargs.get('id')
        article = Article.objects.filter(id=article_id).first()

        if not article:
            raise NotFound(detail="Maqola topilmadi.")

        favorite = Favorite.objects.filter(user=request.user, article=article).first()

        if favorite:
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({"detail": "Maqola topilmadi."}, status=status.HTTP_404_NOT_FOUND)