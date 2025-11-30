from typing import Dict, Any, Optional, Sequence
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Category, Tag, FAQ, SOP, PolicyExplanation, TrainingArticle


class CategoryService:
    """Service for category operations and helpers."""

    @classmethod
    def base_queryset(cls):
        return Category.objects.all().order_by('name')

    @classmethod
    def get_category_list_queryset(cls, params):
        """Build the category list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset

    @staticmethod
    def _apply_filters(queryset, params):
        is_active = params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    @classmethod
    def get_category_by_id(cls, category_id):
        """Get a category by ID."""
        return get_object_or_404(Category, id=category_id)

    @classmethod
    def create_category(cls, validated_data):
        """Create a new category."""
        return Category.objects.create(**validated_data)

    @classmethod
    def update_category(cls, instance, validated_data):
        """Update an existing category."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class TagService:
    """Service for tag operations and helpers."""

    @classmethod
    def base_queryset(cls):
        return Tag.objects.all().order_by('name')

    @classmethod
    def get_tag_list_queryset(cls, params):
        """Build the tag list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset

    @staticmethod
    def _apply_filters(queryset, params):
        search = params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset

    @classmethod
    def get_tag_by_id(cls, tag_id):
        """Get a tag by ID."""
        return get_object_or_404(Tag, id=tag_id)

    @classmethod
    def create_tag(cls, validated_data):
        """Create a new tag."""
        return Tag.objects.create(**validated_data)

    @classmethod
    def update_tag(cls, instance, validated_data):
        """Update an existing tag."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class FAQService:
    """Service for FAQ operations and helpers."""

    LIST_SELECT_RELATED: Sequence[str] = ('category', 'created_by', 'updated_by')
    LIST_PREFETCH_RELATED: Sequence[str] = ('tags',)

    @classmethod
    def base_queryset(cls):
        return FAQ.objects.all().select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED)

    @classmethod
    def get_faq_list_queryset(cls, params):
        """Build the FAQ list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset.order_by('-created_at')

    @staticmethod
    def _apply_filters(queryset, params):
        is_published = params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        category_id = params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(question__icontains=search) | Q(answer__icontains=search)
            )

        return queryset

    @classmethod
    def get_faq_by_id(cls, faq_id):
        """Get a FAQ by ID."""
        return get_object_or_404(
            FAQ.objects.select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED),
            id=faq_id
        )

    @classmethod
    def create_faq(cls, validated_data, user):
        """Create a new FAQ."""
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)

        if category_id:
            validated_data['category_id'] = category_id

        validated_data['created_by'] = user
        validated_data['updated_by'] = user

        faq = FAQ.objects.create(**validated_data)

        if tag_ids:
            faq.tags.set(tag_ids)

        return faq

    @classmethod
    def update_faq(cls, instance, validated_data, user):
        """Update an existing FAQ."""
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)

        if category_id is not None:
            validated_data['category_id'] = category_id

        validated_data['updated_by'] = user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if tag_ids is not None:
            instance.tags.set(tag_ids)

        return instance

    @classmethod
    def increment_view_count(cls, faq):
        """Increment the view count for a FAQ."""
        faq.view_count += 1
        faq.save(update_fields=['view_count'])
        return faq

    @classmethod
    def mark_helpful(cls, faq, is_helpful=True):
        """Mark a FAQ as helpful or not helpful."""
        if is_helpful:
            faq.helpful_count += 1
        else:
            faq.not_helpful_count += 1
        faq.save(update_fields=['helpful_count', 'not_helpful_count'])
        return {
            'helpful_count': faq.helpful_count,
            'not_helpful_count': faq.not_helpful_count
        }


class SOPService:
    """Service for SOP operations and helpers."""

    LIST_SELECT_RELATED: Sequence[str] = ('category', 'created_by', 'updated_by', 'approved_by')
    LIST_PREFETCH_RELATED: Sequence[str] = ('tags',)

    @classmethod
    def base_queryset(cls):
        return SOP.objects.all().select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED)

    @classmethod
    def get_sop_list_queryset(cls, params):
        """Build the SOP list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset.order_by('-created_at')

    @staticmethod
    def _apply_filters(queryset, params):
        is_published = params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        status_filter = params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        category_id = params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        return queryset

    @classmethod
    def get_sop_by_id(cls, sop_id):
        """Get a SOP by ID."""
        return get_object_or_404(
            SOP.objects.select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED),
            id=sop_id
        )

    @classmethod
    def create_sop(cls, validated_data, user):
        """Create a new SOP."""
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)

        if category_id:
            validated_data['category_id'] = category_id

        validated_data['created_by'] = user
        validated_data['updated_by'] = user

        sop = SOP.objects.create(**validated_data)

        if tag_ids:
            sop.tags.set(tag_ids)

        return sop

    @classmethod
    def update_sop(cls, instance, validated_data, user):
        """Update an existing SOP."""
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)

        if category_id is not None:
            validated_data['category_id'] = category_id

        validated_data['updated_by'] = user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if tag_ids is not None:
            instance.tags.set(tag_ids)

        return instance

    @classmethod
    def increment_view_count(cls, sop):
        """Increment the view count for a SOP."""
        sop.view_count += 1
        sop.save(update_fields=['view_count'])
        return sop

    @classmethod
    def approve_sop(cls, sop, user):
        """Approve a SOP."""
        sop.status = 'approved'
        sop.approved_by = user
        sop.save(update_fields=['status', 'approved_by', 'approved_at'])
        return sop


class PolicyExplanationService:
    """Service for PolicyExplanation operations and helpers."""

    LIST_SELECT_RELATED: Sequence[str] = ('category', 'created_by', 'updated_by')
    LIST_PREFETCH_RELATED: Sequence[str] = ('tags',)

    @classmethod
    def base_queryset(cls):
        return PolicyExplanation.objects.all().select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED)

    @classmethod
    def get_policy_explanation_list_queryset(cls, params):
        """Build the PolicyExplanation list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset.order_by('-created_at')

    @staticmethod
    def _apply_filters(queryset, params):
        is_published = params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        category_id = params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search) | Q(policy_reference__icontains=search)
            )

        return queryset

    @classmethod
    def get_policy_explanation_by_id(cls, policy_id):
        """Get a PolicyExplanation by ID."""
        return get_object_or_404(
            PolicyExplanation.objects.select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED),
            id=policy_id
        )

    @classmethod
    def create_policy_explanation(cls, validated_data, user):
        """Create a new PolicyExplanation."""
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)

        if category_id:
            validated_data['category_id'] = category_id

        validated_data['created_by'] = user
        validated_data['updated_by'] = user

        policy = PolicyExplanation.objects.create(**validated_data)

        if tag_ids:
            policy.tags.set(tag_ids)

        return policy

    @classmethod
    def update_policy_explanation(cls, instance, validated_data, user):
        """Update an existing PolicyExplanation."""
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)

        if category_id is not None:
            validated_data['category_id'] = category_id

        validated_data['updated_by'] = user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if tag_ids is not None:
            instance.tags.set(tag_ids)

        return instance

    @classmethod
    def increment_view_count(cls, policy):
        """Increment the view count for a PolicyExplanation."""
        policy.view_count += 1
        policy.save(update_fields=['view_count'])
        return policy


class TrainingArticleService:
    """Service for TrainingArticle operations and helpers."""

    LIST_SELECT_RELATED: Sequence[str] = ('category', 'created_by', 'updated_by')
    LIST_PREFETCH_RELATED: Sequence[str] = ('tags',)

    @classmethod
    def base_queryset(cls):
        return TrainingArticle.objects.all().select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED)

    @classmethod
    def get_training_article_list_queryset(cls, params):
        """Build the TrainingArticle list queryset with all filters applied."""
        queryset = cls.base_queryset()
        queryset = cls._apply_filters(queryset, params)
        return queryset.order_by('-created_at')

    @staticmethod
    def _apply_filters(queryset, params):
        is_published = params.get('is_published')
        if is_published is not None:
            queryset = queryset.filter(is_published=is_published.lower() == 'true')

        category_id = params.get('category_id')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        difficulty_level = params.get('difficulty_level')
        if difficulty_level:
            queryset = queryset.filter(difficulty_level=difficulty_level)

        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(content__icontains=search) | Q(summary__icontains=search)
            )

        return queryset

    @classmethod
    def get_training_article_by_id(cls, article_id):
        """Get a TrainingArticle by ID."""
        return get_object_or_404(
            TrainingArticle.objects.select_related(*cls.LIST_SELECT_RELATED).prefetch_related(*cls.LIST_PREFETCH_RELATED),
            id=article_id
        )

    @classmethod
    def create_training_article(cls, validated_data, user):
        """Create a new TrainingArticle."""
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)

        if category_id:
            validated_data['category_id'] = category_id

        validated_data['created_by'] = user
        validated_data['updated_by'] = user

        article = TrainingArticle.objects.create(**validated_data)

        if tag_ids:
            article.tags.set(tag_ids)

        return article

    @classmethod
    def update_training_article(cls, instance, validated_data, user):
        """Update an existing TrainingArticle."""
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)

        if category_id is not None:
            validated_data['category_id'] = category_id

        validated_data['updated_by'] = user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if tag_ids is not None:
            instance.tags.set(tag_ids)

        return instance

    @classmethod
    def increment_view_count(cls, article):
        """Increment the view count for a TrainingArticle."""
        article.view_count += 1
        article.save(update_fields=['view_count'])
        return article

