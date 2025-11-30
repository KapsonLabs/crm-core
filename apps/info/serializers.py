from rest_framework import serializers
from .models import Category, Tag, FAQ, SOP, PolicyExplanation, TrainingArticle, TrainingArticleRead
from django.contrib.auth import get_user_model

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'slug', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'created_at']
        read_only_fields = ['id', 'created_at']


class FAQSerializer(serializers.ModelSerializer):
    """Serializer for FAQ model."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True)
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'question', 'answer', 'category', 'category_id', 'tags', 'tag_ids',
            'is_published', 'view_count', 'helpful_count', 'not_helpful_count',
            'created_by', 'created_by_email', 'updated_by', 'updated_by_email',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'view_count', 'helpful_count', 'not_helpful_count',
            'created_at', 'updated_at', 'published_at'
        ]
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)
        
        if category_id:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        faq = FAQ.objects.create(**validated_data)
        
        if tag_ids:
            faq.tags.set(tag_ids)
        
        return faq
    
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)
        
        if category_id is not None:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class SOPSerializer(serializers.ModelSerializer):
    """Serializer for SOP model."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True)
    approved_by_email = serializers.EmailField(source='approved_by.email', read_only=True)
    
    class Meta:
        model = SOP
        fields = [
            'id', 'title', 'content', 'version', 'category', 'category_id', 'tags', 'tag_ids',
            'status', 'status_display', 'is_published', 'view_count',
            'created_by', 'created_by_email', 'updated_by', 'updated_by_email',
            'approved_by', 'approved_by_email', 'created_at', 'updated_at',
            'published_at', 'approved_at'
        ]
        read_only_fields = [
            'id', 'view_count', 'created_at', 'updated_at', 'published_at', 'approved_at'
        ]
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)
        
        if category_id:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        sop = SOP.objects.create(**validated_data)
        
        if tag_ids:
            sop.tags.set(tag_ids)
        
        return sop
    
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)
        
        if category_id is not None:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class PolicyExplanationSerializer(serializers.ModelSerializer):
    """Serializer for PolicyExplanation model."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True)
    
    class Meta:
        model = PolicyExplanation
        fields = [
            'id', 'title', 'content', 'policy_reference', 'category', 'category_id',
            'tags', 'tag_ids', 'is_published', 'view_count',
            'created_by', 'created_by_email', 'updated_by', 'updated_by_email',
            'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'view_count', 'created_at', 'updated_at', 'published_at'
        ]
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)
        
        if category_id:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        policy = PolicyExplanation.objects.create(**validated_data)
        
        if tag_ids:
            policy.tags.set(tag_ids)
        
        return policy
    
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)
        
        if category_id is not None:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class TrainingArticleSerializer(serializers.ModelSerializer):
    """Serializer for TrainingArticle model."""
    category = CategorySerializer(read_only=True)
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    difficulty_level_display = serializers.CharField(source='get_difficulty_level_display', read_only=True)
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    updated_by_email = serializers.EmailField(source='updated_by.email', read_only=True)
    
    class Meta:
        model = TrainingArticle
        fields = [
            'id', 'title', 'summary', 'content', 'category', 'category_id', 'tags', 'tag_ids',
            'difficulty_level', 'difficulty_level_display', 'estimated_read_time',
            'is_published', 'is_compulsory', 'view_count', 'created_by', 'created_by_email',
            'updated_by', 'updated_by_email', 'created_at', 'updated_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'view_count', 'created_at', 'updated_at', 'published_at'
        ]
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id', None)
        
        if category_id:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
            validated_data['updated_by'] = request.user
        
        article = TrainingArticle.objects.create(**validated_data)
        
        if tag_ids:
            article.tags.set(tag_ids)
        
        return article
    
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)
        
        if category_id is not None:
            validated_data['category_id'] = category_id
        
        request = self.context.get('request')
        if request and request.user:
            validated_data['updated_by'] = request.user
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class TrainingArticleReadSerializer(serializers.ModelSerializer):
    """Serializer for TrainingArticleRead model."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    training_article_title = serializers.CharField(source='training_article.title', read_only=True)
    
    class Meta:
        model = TrainingArticleRead
        fields = [
            'id', 'user', 'user_email', 'user_full_name', 'training_article',
            'training_article_title', 'read_at', 'completed_at'
        ]
        read_only_fields = ['id', 'read_at', 'completed_at']

