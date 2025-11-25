from django.core.management.base import BaseCommand
from django.db import transaction
from apps.accounts.models import Module, Permission, Role


class Command(BaseCommand):
    help = 'Seed modules, permissions, and roles'

    def handle(self, *args, **options):
        self.stdout.write('Seeding modules, permissions, and roles...')
        
        with transaction.atomic():
            # Step 1: Create Modules
            self.stdout.write('\n1. Creating modules...')
            modules_data = [
                {'id': 1, 'name': 'Accounts', 'description': 'User accounts and authentication management'},
                {'id': 2, 'name': 'CRM', 'description': 'Customer Relationship Management - tickets, messages, and notifications'},
                {'id': 3, 'name': 'KPIs', 'description': 'Key Performance Indicators - KPIs, KPI reports, and KPI actions'},
            ]
            
            modules = {}
            for module_data in modules_data:
                module, created = Module.objects.get_or_create(
                    id=module_data['id'],
                    defaults={
                        'name': module_data['name'],
                        'description': module_data['description'],
                        'is_active': True
                    }
                )
                modules[module_data['name']] = module
                status = 'Created' if created else 'Already exists'
                self.stdout.write(f'  {status}: {module.name}')
            
            # Step 2: Create Permissions
            self.stdout.write('\n2. Creating permissions...')
            permissions_data = [
                # Accounts permissions
                {'module': 'Accounts', 'action': 'create', 'name': 'Create Accounts', 'codename': 'accounts_create'},
                {'module': 'Accounts', 'action': 'read', 'name': 'Read Accounts', 'codename': 'accounts_read'},
                {'module': 'Accounts', 'action': 'update', 'name': 'Update Accounts', 'codename': 'accounts_update'},
                {'module': 'Accounts', 'action': 'delete', 'name': 'Delete Accounts', 'codename': 'accounts_delete'},
                {'module': 'Accounts', 'action': 'create_role', 'name': 'Create Roles', 'codename': 'accounts_create_role'},
                {'module': 'Accounts', 'action': 'read_role', 'name': 'Read Roles', 'codename': 'accounts_read_role'},
                {'module': 'Accounts', 'action': 'update_role', 'name': 'Update Roles', 'codename': 'accounts_update_role'},
                {'module': 'Accounts', 'action': 'delete_role', 'name': 'Delete Roles', 'codename': 'accounts_delete_role'},
                
                # CRM permissions
                {'module': 'CRM', 'action': 'create_ticket', 'name': 'Create CRM Tickets', 'codename': 'crm_create_ticket'},
                {'module': 'CRM', 'action': 'read_ticket', 'name': 'Read CRM Tickets', 'codename': 'crm_read_ticket'},
                {'module': 'CRM', 'action': 'update_ticket', 'name': 'Update CRM Tickets', 'codename': 'crm_update_ticket'},
                {'module': 'CRM', 'action': 'delete_ticket', 'name': 'Delete CRM Tickets', 'codename': 'crm_delete_ticket'},
                {'module': 'CRM', 'action': 'create_message', 'name': 'Create CRM Messages', 'codename': 'crm_create_message'},
                {'module': 'CRM', 'action': 'read_message', 'name': 'Read CRM Messages', 'codename': 'crm_read_message'},
                {'module': 'CRM', 'action': 'read_notification', 'name': 'Read CRM Notifications', 'codename': 'crm_read_notification'},
                {'module': 'CRM', 'action': 'manage', 'name': 'Manage CRM', 'codename': 'crm_manage'},

                # KPIs permissions
                {'module': 'KPIs', 'action': 'create_kpi', 'name': 'Create KPIs', 'codename': 'kpis_create_kpi'},
                {'module': 'KPIs', 'action': 'read_kpi', 'name': 'Read KPIs', 'codename': 'kpis_read_kpi'},
                {'module': 'KPIs', 'action': 'update_kpi', 'name': 'Update KPIs', 'codename': 'kpis_update_kpi'},
                {'module': 'KPIs', 'action': 'delete_kpi', 'name': 'Delete KPIs', 'codename': 'kpis_delete_kpi'},
                {'module': 'KPIs', 'action': 'create_kpi_report', 'name': 'Create KPI Reports', 'codename': 'kpis_create_kpi_report'},
                {'module': 'KPIs', 'action': 'approve_kpi_report', 'name': 'Approve KPI Reports', 'codename': 'kpis_approve_kpi_report'},

            ]
            
            permissions = {}
            for perm_data in permissions_data:
                module = modules[perm_data['module']]
                permission, created = Permission.objects.get_or_create(
                    codename=perm_data['codename'],
                    defaults={
                        'name': perm_data['name'],
                        'resource': module,
                        'action': perm_data['action'],
                        'is_active': True
                    }
                )
                permissions[perm_data['codename']] = permission
                status = 'Created' if created else 'Already exists'
                self.stdout.write(f'  {status}: {permission.name}')
            
            # Step 3: Create Roles with Permissions
            self.stdout.write('\n3. Creating roles...')
            
            roles_config = {
                'Admin': {
                    'slug': 'admin',
                    'description': 'Administrator with full access to all system functions',
                    'role_type': 'system',
                    'permissions': [
                        # All Accounts permissions
                        'accounts_create', 'accounts_read', 'accounts_update', 'accounts_delete',
                        'accounts_create_role', 'accounts_read_role', 'accounts_update_role', 'accounts_delete_role',
                        # All CRM permissions
                        'crm_create_ticket', 'crm_read_ticket', 'crm_update_ticket', 'crm_delete_ticket',
                        'crm_create_message', 'crm_read_message', 'crm_read_notification', 'crm_manage',
                    ]
                },
                'Supervisor': {
                    'slug': 'manager',
                    'description': 'Manager with access to CRM and user management',
                    'role_type': 'system',
                    'permissions': [
                        # Accounts read and update
                        'accounts_read', 'accounts_update',
                        'accounts_read_role',
                        # Full CRM access
                        'crm_create_ticket', 'crm_read_ticket', 'crm_update_ticket', 'crm_delete_ticket',
                        'crm_create_message', 'crm_read_message', 'crm_read_notification', 'crm_manage',
                        # Full KPIs access
                        'kpis_create_kpi', 'kpis_read_kpi', 'kpis_update_kpi', 'kpis_delete_kpi',
                        'kpis_create_kpi_report', 'kpis_approve_kpi_report',
                    ]
                },
                'Support Agent': {
                    'slug': 'support-agent',
                    'description': 'Support agent with access to CRM tickets and messages',
                    'role_type': 'system',
                    'permissions': [
                        # Limited accounts access
                        'accounts_read',
                        # Full CRM ticket access
                        'crm_create_ticket', 'crm_read_ticket', 'crm_update_ticket',
                        'crm_create_message', 'crm_read_message', 'crm_read_notification',
                        # Full KPIs access
                        'kpis_create_kpi_report'
                    ]
                },
                'Viewer': {
                    'slug': 'viewer',
                    'description': 'Viewer with read-only access',
                    'role_type': 'system',
                    'permissions': [
                        # Read-only access
                        'accounts_read', 'accounts_read_role',
                        'crm_read_ticket', 'crm_read_message', 'crm_read_notification',
                    ]
                },
            }
            
            total_roles_created = 0
            total_roles_updated = 0
            
            for role_name, config in roles_config.items():
                slug = config['slug']
                
                # Check if role already exists
                role, created = Role.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': role_name,
                        'description': config['description'],
                        'role_type': config['role_type'],
                        'is_active': True
                    }
                )
                
                # Update permissions for the role
                permission_objects = []
                for perm_codename in config['permissions']:
                    if perm_codename in permissions:
                        permission_objects.append(permissions[perm_codename])
                
                # Set permissions (this will update existing roles too)
                role.permissions.set(permission_objects)
                
                if created:
                    total_roles_created += 1
                    status_text = 'Created'
                else:
                    total_roles_updated += 1
                    status_text = 'Updated'
                
                self.stdout.write(
                    f'  {status_text}: {role.name} ({len(permission_objects)} permissions)'
                )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully seeded:\n'
                    f'  - {len(modules)} modules\n'
                    f'  - {len(permissions)} permissions\n'
                    f'  - {total_roles_created} roles created\n'
                    f'  - {total_roles_updated} roles updated'
                )
            )
            
            # Display summary
            self.stdout.write('\n=== ROLE SUMMARY ===')
            for role in Role.objects.all().order_by('name'):
                perm_count = role.permissions.count()
                self.stdout.write(f'  - {role.name} ({role.slug}): {perm_count} permissions')

