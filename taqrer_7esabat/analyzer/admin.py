from django.contrib import admin
from .models import UploadedFile, AnalysisResult


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ['original_filename', 'file_size_display', 'status', 'uploaded_at']
    list_filter = ['status', 'uploaded_at']
    search_fields = ['original_filename']
    readonly_fields = ['uploaded_at']


@admin.register(AnalysisResult)
class AnalysisResultAdmin(admin.ModelAdmin):
    list_display = ['uploaded_file', 'row_count', 'col_count', 'sheet_name', 'created_at']
    readonly_fields = ['created_at']
