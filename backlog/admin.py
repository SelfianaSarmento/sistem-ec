from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Release, ECS, DocumentVersion, AuditLog


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'active', 'is_staff']
    list_filter = ['role', 'active']
    fieldsets = UserAdmin.fieldsets + (
        ('Perfil EC', {'fields': ('role', 'active')}),
    )


@admin.register(Release)
class ReleaseAdmin(admin.ModelAdmin):
    list_display = ['release_code', 'year', 'number_sequency', 'production_go_live_date', 'is_open']
    list_filter = ['year']


@admin.register(ECS)
class ECSAdmin(admin.ModelAdmin):
    list_display = ['esc_code', 'cr_rt_me_reference', 'status', 'id_solicitante', 'cd_responsavel_id', 'creation_date']
    list_filter = ['status', 'year']
    search_fields = ['esc_code', 'description', 'cr_rt_me_reference']


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['ec', 'version_number', 'uploaded_by', 'upload_date']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['ec', 'user', 'action', 'data_hora']
    list_filter = ['action']
    readonly_fields = ['ec', 'user', 'action', 'detail', 'data_hora']