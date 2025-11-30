from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    CategorySerializer,
    TagSerializer,
    FAQSerializer,
    SOPSerializer,
    PolicyExplanationSerializer,
    TrainingArticleSerializer,
)
from .services import (
    CategoryService,
    TagService,
    FAQService,
    SOPService,
    PolicyExplanationService,
    TrainingArticleService,
)


# -----------------------------------------------------------------------------
# Category Views
# -----------------------------------------------------------------------------

class CategoryListCreateView(APIView):
    """List all categories or create a new category."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all categories."""
        params = request.query_params.dict()
        queryset = CategoryService.get_category_list_queryset(params)
        serializer = CategorySerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new category."""
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            category = CategoryService.create_category(serializer.validated_data)
            serializer = CategorySerializer(category)
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailView(APIView):
    """Retrieve or update a category."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a category."""
        category = CategoryService.get_category_by_id(id)
        serializer = CategorySerializer(category)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a category."""
        category = CategoryService.get_category_by_id(id)
        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            category = CategoryService.update_category(category, serializer.validated_data)
            serializer = CategorySerializer(category)
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Tag Views
# -----------------------------------------------------------------------------

class TagListCreateView(APIView):
    """List all tags or create a new tag."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all tags."""
        params = request.query_params.dict()
        queryset = TagService.get_tag_list_queryset(params)
        serializer = TagSerializer(queryset, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new tag."""
        serializer = TagSerializer(data=request.data)
        if serializer.is_valid():
            tag = TagService.create_tag(serializer.validated_data)
            serializer = TagSerializer(tag)
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TagDetailView(APIView):
    """Retrieve or update a tag."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a tag."""
        tag = TagService.get_tag_by_id(id)
        serializer = TagSerializer(tag)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a tag."""
        tag = TagService.get_tag_by_id(id)
        serializer = TagSerializer(tag, data=request.data)
        if serializer.is_valid():
            tag = TagService.update_tag(tag, serializer.validated_data)
            serializer = TagSerializer(tag)
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# FAQ Views
# -----------------------------------------------------------------------------

class FAQListCreateView(APIView):
    """List all FAQs or create a new FAQ."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all FAQs."""
        params = request.query_params.dict()
        queryset = FAQService.get_faq_list_queryset(params)
        serializer = FAQSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new FAQ."""
        serializer = FAQSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            faq = FAQService.create_faq(serializer.validated_data, request.user)
            serializer = FAQSerializer(faq, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response({"data": serializer.errors, "status": 400}, status=status.HTTP_400_BAD_REQUEST)


class FAQDetailView(APIView):
    """Retrieve or update a FAQ."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a FAQ and increment view count."""
        faq = FAQService.get_faq_by_id(id)
        FAQService.increment_view_count(faq)
        serializer = FAQSerializer(faq, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a FAQ."""
        faq = FAQService.get_faq_by_id(id)
        serializer = FAQSerializer(faq, data=request.data, context={'request': request})
        if serializer.is_valid():
            faq = FAQService.update_faq(faq, serializer.validated_data, request.user)
            serializer = FAQSerializer(faq, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FAQHelpfulView(APIView):
    """Mark a FAQ as helpful or not helpful."""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        """Mark a FAQ as helpful or not helpful."""
        faq = FAQService.get_faq_by_id(id)
        is_helpful = request.data.get('is_helpful', True)
        result = FAQService.mark_helpful(faq, is_helpful)
        return Response({"data": result, "status": 200}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# SOP Views
# -----------------------------------------------------------------------------

class SOPListCreateView(APIView):
    """List all SOPs or create a new SOP."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all SOPs."""
        params = request.query_params.dict()
        queryset = SOPService.get_sop_list_queryset(params)
        serializer = SOPSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new SOP."""
        serializer = SOPSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            sop = SOPService.create_sop(serializer.validated_data, request.user)
            serializer = SOPSerializer(sop, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SOPDetailView(APIView):
    """Retrieve or update a SOP."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a SOP and increment view count."""
        sop = SOPService.get_sop_by_id(id)
        SOPService.increment_view_count(sop)
        serializer = SOPSerializer(sop, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a SOP."""
        sop = SOPService.get_sop_by_id(id)
        serializer = SOPSerializer(sop, data=request.data, context={'request': request})
        if serializer.is_valid():
            sop = SOPService.update_sop(sop, serializer.validated_data, request.user)
            serializer = SOPSerializer(sop, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SOPApproveView(APIView):
    """Approve a SOP."""
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        """Approve a SOP."""
        sop = SOPService.get_sop_by_id(id)
        sop = SOPService.approve_sop(sop, request.user)
        serializer = SOPSerializer(sop, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# Policy Explanation Views
# -----------------------------------------------------------------------------

class PolicyExplanationListCreateView(APIView):
    """List all policy explanations or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all policy explanations."""
        params = request.query_params.dict()
        queryset = PolicyExplanationService.get_policy_explanation_list_queryset(params)
        serializer = PolicyExplanationSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new policy explanation."""
        serializer = PolicyExplanationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            policy = PolicyExplanationService.create_policy_explanation(serializer.validated_data, request.user)
            serializer = PolicyExplanationSerializer(policy, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PolicyExplanationDetailView(APIView):
    """Retrieve or update a policy explanation."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a policy explanation and increment view count."""
        policy = PolicyExplanationService.get_policy_explanation_by_id(id)
        PolicyExplanationService.increment_view_count(policy)
        serializer = PolicyExplanationSerializer(policy, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a policy explanation."""
        policy = PolicyExplanationService.get_policy_explanation_by_id(id)
        serializer = PolicyExplanationSerializer(policy, data=request.data, context={'request': request})
        if serializer.is_valid():
            policy = PolicyExplanationService.update_policy_explanation(policy, serializer.validated_data, request.user)
            serializer = PolicyExplanationSerializer(policy, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Training Article Views
# -----------------------------------------------------------------------------

class TrainingArticleListCreateView(APIView):
    """List all training articles or create a new one."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all training articles."""
        params = request.query_params.dict()
        queryset = TrainingArticleService.get_training_article_list_queryset(params)
        serializer = TrainingArticleSerializer(queryset, many=True, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def post(self, request):
        """Create a new training article."""
        serializer = TrainingArticleSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            article = TrainingArticleService.create_training_article(serializer.validated_data, request.user)
            serializer = TrainingArticleSerializer(article, context={'request': request})
            return Response({"data": serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TrainingArticleDetailView(APIView):
    """Retrieve or update a training article."""
    permission_classes = [IsAuthenticated]

    def get(self, request, id):
        """Retrieve a training article and increment view count."""
        article = TrainingArticleService.get_training_article_by_id(id)
        TrainingArticleService.increment_view_count(article)
        serializer = TrainingArticleSerializer(article, context={'request': request})
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)

    def put(self, request, id):
        """Update a training article."""
        article = TrainingArticleService.get_training_article_by_id(id)
        serializer = TrainingArticleSerializer(article, data=request.data, context={'request': request})
        if serializer.is_valid():
            article = TrainingArticleService.update_training_article(article, serializer.validated_data, request.user)
            serializer = TrainingArticleSerializer(article, context={'request': request})
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

