from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.views import (
    TokenRefreshView as SimpleJWTTokenRefreshView,
    TokenVerifyView as SimpleJWTTokenVerifyView
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from collections import defaultdict

from .models import User, Permission, Module, Role
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    PermissionSerializer, PermissionCreateSerializer,
    ModuleSerializer, RoleSerializer,
    ChangePasswordSerializer,
    RegisterSerializer,
    LoginCredentialsSerializer
)
from apps.accounts.serializers import BranchDetailsSerializer
from .services import (
    get_user_by_id,
    update_user,
    deactivate_user,
    activate_user,
    set_session_cookie,
    serialize_user,
    get_ws_endpoints
)

from django.contrib.auth import login


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

class LoginView(APIView):
    """Login view that returns JWT tokens and creates a session for WebSocket authentication."""

    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = LoginCredentialsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Create Django session
        login(request, user)
        request.session.save()

        # Build response payload
        response_data = {
            "refresh": str(refresh := RefreshToken.for_user(user)),
            "access": str(refresh.access_token),
            "user": serialize_user(user),
            "websocket_endpoints": get_ws_endpoints(request),
        }

        response = Response(response_data, status=status.HTTP_200_OK)

        # Set session cookie manually for frontend JS & WebSockets
        set_session_cookie(request, response)

        return response



class RefreshTokenView(SimpleJWTTokenRefreshView):
    
    permission_classes = [AllowAny]


class VerifyTokenView(SimpleJWTTokenVerifyView):
   
    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    Note: Token blacklisting requires 'rest_framework_simplejwt.token_blacklist' in INSTALLED_APPS.
    If not installed, this endpoint will still return success but won't blacklist the token.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Logout user by blacklisting refresh token."""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                
                # Try to blacklist the token if blacklist app is installed
                try:
                    token.blacklist()
                except AttributeError:
                    # Token blacklist app not installed, just return success
                    # The token will expire naturally based on its lifetime
                    pass
                
                return Response({
                    "status": 200,
                    "message": "Successfully logged out"
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "status": 400,
                    "error": "Refresh token is required"
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "status": 400,
                "error": f"Invalid token: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# USER VIEWS
# ============================================================================

class UserListView(APIView):
    """List all users or create a new user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request) -> Response:
        """List all users."""
        users = User.objects.select_related('role', 'organization', 'branch').all()
        
        # Filter by organization_id if provided
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            users = users.filter(organization_id=organization_id)
        
        serializer = UserSerializer(users, many=True)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class UserDetailView(APIView):
    """Get user details by ID."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request, user_id: str) -> Response:
        user = get_user_by_id(user_id)
        if not user:
            return Response(
                {"status": 404, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UserSerializer(user)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class UserUpdateView(APIView):
    """Update user information."""
    
    permission_classes = [IsAuthenticated]
    
    def put(self, request: Request, user_id: str) -> Response:
        user = get_user_by_id(user_id)
        if not user:
            return Response(
                {"status": 404, "message": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        try:
            updated_user = update_user(user, serializer.validated_data)
            response_serializer = UserSerializer(updated_user)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserDeactivateView(APIView):
    """Deactivate a user account."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request, user_id: str) -> Response:
        user = get_user_by_id(user_id)
        if not user:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            deactivate_user(user)
            return Response(
                {"detail": "User deactivated successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserActivateView(APIView):
    """Activate a user account."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request, user_id: str) -> Response:
        user = get_user_by_id(user_id)
        if not user:
            return Response(
                {"detail": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            activate_user(user)
            return Response(
                {"detail": "User activated successfully"},
                status=status.HTTP_200_OK
            )
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ChangePasswordView(APIView):
    """Change user password."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request: Request) -> Response:
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response(
                {"detail": "Password changed successfully"},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    """Get current authenticated user."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request: Request) -> Response:
        serializer = UserSerializer(request.user)
        return Response({"status": 200, "data": serializer.data}, status=status.HTTP_200_OK)


class CurrentUserPermissionsView(APIView):
    """Get current authenticated user's permissions."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all permissions for the current user."""
        user = request.user
        
        permissions_list = []
        if user.role and user.role.is_active:
            permissions_list = user.role.get_permissions_list()
        
        # Group permissions by module
        permissions_by_module = defaultdict(list)
        permissions = Permission.objects.filter(
            codename__in=permissions_list,
            is_active=True
        ).select_related('resource')
        
        for permission in permissions:
            module = permission.resource
            permissions_by_module[module].append({
                'id': str(permission.id),
                'name': permission.name,
                'codename': permission.codename,
                'description': permission.description,
                'action': permission.action,
                'action_display': permission.get_action_display(),
            })
        
        # Convert to list format
        permissions_grouped = []
        for module, perms in permissions_by_module.items():
            permissions_grouped.append({
                'module_id': module.id,
                'module_name': module.name,
                'module_description': module.description,
                'permissions': perms,
                'permissions_count': len(perms)
            })
        
        response_data = {
            'user_id': str(user.id),
            'email': user.email,
            'full_name': user.get_full_name() or user.email,
            'is_superuser': user.is_superuser,
            'role': RoleSerializer(user.role).data if user.role else None,
            'permissions_by_module': permissions_grouped,
            'all_permissions_codenames': sorted(permissions_list),
            'total_unique_permissions': len(permissions_list)
        }
        
        return Response({"data": response_data, "status": 200}, status=status.HTTP_200_OK)


# ============================================================================
# MODULE VIEWS
# ============================================================================

class ModuleListView(APIView):
    """List all modules."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all modules with optional filtering."""
        modules = Module.objects.all()
        
        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            modules = modules.filter(is_active=is_active.lower() == 'true')
        
        # Search by name
        search = request.query_params.get('search')
        if search:
            modules = modules.filter(name__icontains=search)
        
        serializer = ModuleSerializer(modules, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)


class ModuleDetailView(APIView):
    """Get module details with all its permissions."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, module_id):
        """Get module details."""
        module = get_object_or_404(Module, pk=module_id)
        
        # Get module data
        module_serializer = ModuleSerializer(module)
        
        # Get all permissions for this module
        permissions = module.permissions.filter(is_active=True)
        permissions_serializer = PermissionSerializer(permissions, many=True)
        
        response_data = module_serializer.data
        response_data['permissions'] = permissions_serializer.data
        
        return Response({"data": response_data, "status": 200}, status=status.HTTP_200_OK)


# ============================================================================
# PERMISSION VIEWS
# ============================================================================

class PermissionListCreateView(APIView):
    """
    List all permissions grouped by module or create a new permission.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all permissions grouped by module with optional filtering."""
        
        permissions = Permission.objects.select_related('resource').all()
        
        # Filter by resource (module ID)
        resource = request.query_params.get('resource')
        if resource:
            permissions = permissions.filter(resource_id=resource)
        
        # Filter by action
        action = request.query_params.get('action')
        if action:
            permissions = permissions.filter(action=action)
        
        # Filter by active status
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            permissions = permissions.filter(is_active=is_active.lower() == 'true')
        
        # Order by module name and action
        permissions = permissions.order_by('resource__name', 'action')
        
        # Check response format preference
        response_format = request.query_params.get('format', 'grouped')
        
        if response_format == 'flat':
            # Traditional flat list
            serializer = PermissionSerializer(permissions, many=True)
            return Response(
                {
                    "data": serializer.data,
                    "total_permissions": permissions.count(),
                    "status": 200
                },
                status=status.HTTP_200_OK
            )
        
        # Grouped by module (default)
        permissions_by_module = defaultdict(list)
        
        for permission in permissions:
            module = permission.resource
            permissions_by_module[module].append({
                'id': str(permission.id),
                'name': permission.name,
                'codename': permission.codename,
                'description': permission.description,
                'action': permission.action,
                'action_display': permission.get_action_display(),
                'is_active': permission.is_active,
                'created_at': permission.created_at.isoformat() if permission.created_at else None
            })
        
        # Convert to list format
        permissions_grouped = []
        for module, perms in permissions_by_module.items():
            permissions_grouped.append({
                'module_id': module.id,
                'module_name': module.name,
                'module_description': module.description,
                'module_is_active': module.is_active,
                'permissions': perms,
                'permissions_count': len(perms)
            })
        
        # Sort by module name
        permissions_grouped = sorted(permissions_grouped, key=lambda x: x['module_name'])
        
        return Response(
            {
                "data": permissions_grouped,
                "total_modules": len(permissions_grouped),
                "total_permissions": permissions.count(),
                "status": 200
            },
            status=status.HTTP_200_OK
        )
    
    def post(self, request):
        """Create a new permission."""
        serializer = PermissionCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            permission = serializer.save()
            response_serializer = PermissionSerializer(permission)
            return Response(
                {"data": response_serializer.data, "status": 201},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PermissionDetailView(APIView):
    """Retrieve, update, or delete a permission."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, permission_id):
        """Get permission details."""
        permission = get_object_or_404(Permission, pk=permission_id)
        serializer = PermissionSerializer(permission)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
    
    def put(self, request, permission_id):
        """Update a permission."""
        permission = get_object_or_404(Permission, pk=permission_id)
        serializer = PermissionSerializer(permission, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_permission = serializer.save()
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, permission_id):
        """Delete a permission."""
        permission = get_object_or_404(Permission, pk=permission_id)
        permission.delete()
        return Response(
            {"message": "Permission deleted successfully", "status": 204},
            status=status.HTTP_204_NO_CONTENT
        )


# ============================================================================
# ROLE VIEWS
# ============================================================================

class RoleListCreateView(APIView):
    """List all roles or create a new role."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List all roles, filtered by organization_id if provided."""
        roles = Role.objects.prefetch_related('permissions', 'organization').all()
        
        # Filter by organization_id if provided
        organization_id = request.query_params.get('organization_id')
        if organization_id:
            roles = roles.filter(organization_id=organization_id)
        
        serializer = RoleSerializer(roles, many=True)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Create a new role."""
        serializer = RoleSerializer(data=request.data)
        if serializer.is_valid():
            role = serializer.save(created_by=request.user)
            response_serializer = RoleSerializer(role)
            return Response({"data": response_serializer.data, "status": 201}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleDetailView(APIView):
    """Retrieve, update, or delete a role."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, role_id):
        """Get role details."""
        role = get_object_or_404(Role, pk=role_id)
        serializer = RoleSerializer(role)
        return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
    
    def put(self, request, role_id):
        """Update a role."""
        role = get_object_or_404(Role, pk=role_id)
        serializer = RoleSerializer(role, data=request.data, partial=True)
        
        if serializer.is_valid():
            updated_role = serializer.save()
            return Response({"data": serializer.data, "status": 200}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, role_id):
        """Delete a role."""
        role = get_object_or_404(Role, pk=role_id)
        
        # Prevent deletion of system roles
        if role.role_type == 'system':
            return Response(
                {"error": "System roles cannot be deleted", "status": 400},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        role.delete()
        return Response(
            {"message": "Role deleted successfully", "status": 204},
            status=status.HTTP_204_NO_CONTENT
        )

