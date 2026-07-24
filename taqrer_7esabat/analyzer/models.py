from django.db import models
import json


class UploadedFile(models.Model):
    """Model to store uploaded Excel files and their processing status."""
    
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('processing', 'جاري المعالجة'),
        ('completed', 'مكتمل'),
        ('error', 'خطأ'),
    ]
    
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(default=0)  # in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, default='')
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'ملف مرفوع'
        verbose_name_plural = 'ملفات مرفوعة'
    
    def __str__(self):
        return f"{self.original_filename} ({self.get_status_display()})"
    
    @property
    def file_size_display(self):
        """Return human-readable file size."""
        if self.file_size < 1024:
            return f"{self.file_size} بايت"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} كيلوبايت"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} ميجابايت"


class AnalysisResult(models.Model):
    """Model to store analysis results as JSON."""
    
    uploaded_file = models.OneToOneField(
        UploadedFile, on_delete=models.CASCADE, related_name='analysis'
    )
    result_data = models.JSONField(default=dict)
    column_types = models.JSONField(default=dict)
    row_count = models.PositiveIntegerField(default=0)
    col_count = models.PositiveIntegerField(default=0)
    sheet_name = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'نتيجة التحليل'
        verbose_name_plural = 'نتائج التحليل'
    
    def __str__(self):
        return f"تحليل: {self.uploaded_file.original_filename}"
