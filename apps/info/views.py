from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q

from .models import Category, Tag, FAQ, SOP, PolicyExplanation, TrainingArticle
from .serializers import (
    CategorySerializer,
    TagSerializer,
    FAQSerializer,
    SOPSerializer,
    PolicyExplanationSerializer,
    TrainingArticleSerializer,
)


# -----------------------------------------------------------------------------
# Category Views
# -----------------------------------------------------------------------------

class CategoryListCreateView(generics.ListCreateAPIView):
    """List all categories or create a new category."""
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().order_by('name')

    def get_queryset(self):
        queryset = Category.objects.all().order_by('name')
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset


class CategoryDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a category."""
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    lookup_field = 'id'


# -----------------------------------------------------------------------------
# Tag Views
# -----------------------------------------------------------------------------

class TagListCreateView(generics.ListCreateAPIView):
    """List all tags or create a new tag."""
    permission_classes = [IsAuthenticated]
    serializer_class = TagSerializer
    queryset = Tag.objects.all().order_by('name')

    def get_queryset(self):
        queryset = Tag.objects.all().order_by('name')
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset


class TagDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a tag."""
    permission_classes = [IsAuthenticated]
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    lookup_field = 'id'


# -----------------------------------------------------------------------------
# FAQ Views
# -----------------------------------------------------------------------------

class FAQListCreateView(generics.ListCreateAPIView):
    """List all FAQs or create a new FAQ."""
    permission_classes = [IsAuthenticated]
    serializer_class = FAQSerializer

    def get_queryset(self):
        queryset = FAQ.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
        
        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(question__icontains=search) | Q(answer__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class FAQDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a FAQ."""
    permission_classes = [IsAuthenticated]
    serializer_class = FAQSerializer
    queryset = FAQ.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        """Increment view count when FAQ is viewed."""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class FAQHelpfulView(APIView):
    """Mark a FAQ as helpful or not helpful."""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        faq = get_object_or_404(FAQ, id=id)
        is_helpful = request.data.get('is_helpful', True)
        
        if is_helpful:
            faq.helpful_count += 1
        else:
            faq.not_helpful_count += 1
        
        faq.save(update_fields=['helpful_count', 'not_helpful_count'])
        return Response({
            'helpful_count': faq.helpful_count,
            'not_helpful_count': faq.not_helpful_count
        })


# -----------------------------------------------------------------------------
# SOP Views
# -----------------------------------------------------------------------------

class SOPListCreateView(generics.ListCreateAPIView):
    """List all SOPs or create a new SOP."""
    permission_classes = [IsAuthenticated]
    serializer_class = SOPSerializer

    def get_queryset(self):
        queryset = SOP.objects.select_related('category', 'created_by', 'updated_by', 'approved_by').prefetch_related('tags').all()
        
        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class SOPDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a SOP."""
    permission_classes = [IsAuthenticated]
    serializer_class = SOPSerializer
    queryset = SOP.objects.select_related('category', 'created_by', 'updated_by', 'approved_by').prefetch_related('tags').all()
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        """Increment view count when SOP is viewed."""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class SOPApproveView(APIView):
    """Approve a SOP."""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        sop = get_object_or_404(SOP, id=id)
        sop.status = 'approved'
        sop.approved_by = request.user
        sop.save(update_fields=['status', 'approved_by', 'approved_at'])
        
        serializer = SOPSerializer(sop, context={'request': request})
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# Policy Explanation Views
# -----------------------------------------------------------------------------

class PolicyExplanationListCreateView(generics.ListCreateAPIView):
    """List all policy explanations or create a new one."""
    permission_classes = [IsAuthenticated]
    serializer_class = PolicyExplanationSerializer

    def get_queryset(self):
        queryset = PolicyExplanation.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
        
        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search) | Q(policy_reference__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class PolicyExplanationDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a policy explanation."""
    permission_classes = [IsAuthenticated]
    serializer_class = PolicyExplanationSerializer
    queryset = PolicyExplanation.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        """Increment view count when policy explanation is viewed."""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# -----------------------------------------------------------------------------
# Training Article Views
# -----------------------------------------------------------------------------

class TrainingArticleListCreateView(generics.ListCreateAPIView):
    """List all training articles or create a new one."""
    permission_classes = [IsAuthenticated]
    serializer_class = TrainingArticleSerializer

    def get_queryset(self):
        queryset = TrainingArticle.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
        
        # Filter by published status
        is_published = self.request.query_params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')
        
        # Filter by category
        category_id = self.request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by difficulty level
        difficulty_level = self.request.query_params.get('difficulty_level')
        if difficulty_level:
            queryset = queryset.filter(difficulty_level=difficulty_level)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search) | Q(summary__icontains=search)
            )
        
        return queryset.order_by('-created_at')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class TrainingArticleDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a training article."""
    permission_classes = [IsAuthenticated]
    serializer_class = TrainingArticleSerializer
    queryset = TrainingArticle.objects.select_related('category', 'created_by', 'updated_by').prefetch_related('tags').all()
    lookup_field = 'id'

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        """Increment view count when training article is viewed."""
        instance = self.get_object()
        instance.view_count += 1
        instance.save(update_fields=['view_count'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

