from django.urls import path
from .views import (
    # Category views
    CategoryListCreateView,
    CategoryDetailView,
    # Tag views
    TagListCreateView,
    TagDetailView,
    # FAQ views
    FAQListCreateView,
    FAQDetailView,
    FAQHelpfulView,
    # SOP views
    SOPListCreateView,
    SOPDetailView,
    SOPApproveView,
    # Policy Explanation views
    PolicyExplanationListCreateView,
    PolicyExplanationDetailView,
    # Training Article views
    TrainingArticleListCreateView,
    TrainingArticleDetailView,
)

urlpatterns = [
    # Category endpoints
    path('categories/', CategoryListCreateView.as_view(), name='category-list-create'),
    path('categories/<uuid:id>/', CategoryDetailView.as_view(), name='category-detail'),
    
    # Tag endpoints
    path('tags/', TagListCreateView.as_view(), name='tag-list-create'),
    path('tags/<uuid:id>/', TagDetailView.as_view(), name='tag-detail'),
    
    # FAQ endpoints
    path('faqs/', FAQListCreateView.as_view(), name='faq-list-create'),
    path('faqs/<uuid:id>/', FAQDetailView.as_view(), name='faq-detail'),
    path('faqs/<uuid:id>/helpful/', FAQHelpfulView.as_view(), name='faq-helpful'),
    
    # SOP endpoints
    path('sops/', SOPListCreateView.as_view(), name='sop-list-create'),
    path('sops/<uuid:id>/', SOPDetailView.as_view(), name='sop-detail'),
    path('sops/<uuid:id>/approve/', SOPApproveView.as_view(), name='sop-approve'),
    
    # Policy Explanation endpoints
    path('policy-explanations/', PolicyExplanationListCreateView.as_view(), name='policy-explanation-list-create'),
    path('policy-explanations/<uuid:id>/', PolicyExplanationDetailView.as_view(), name='policy-explanation-detail'),
    
    # Training Article endpoints
    path('training-articles/', TrainingArticleListCreateView.as_view(), name='training-article-list-create'),
    path('training-articles/<uuid:id>/', TrainingArticleDetailView.as_view(), name='training-article-detail'),
]

