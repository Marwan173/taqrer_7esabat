from django import forms
import os


class ExcelUploadForm(forms.Form):
    """Form for uploading Excel files with validation."""
    
    file = forms.FileField(
        label='اختر ملف Excel',
        help_text='الصيغ المدعومة: .xlsx, .xls (الحد الأقصى: 50 ميجابايت)',
        widget=forms.FileInput(attrs={
            'accept': '.xlsx,.xls',
            'class': 'form-control',
            'id': 'file-input',
        })
    )
    
    analysis_mode = forms.ChoiceField(
        choices=[('auto', 'تحليل تلقائي'), ('custom', 'تحليل مخصص')],
        initial='auto',
        required=False,
        widget=forms.HiddenInput()
    )
    
    custom_query = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'مثال: قارن المبيعات بين الفروع خلال آخر 3 شهور',
            'id': 'custom-query-input',
        })
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file extension
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in ['.xlsx', '.xls']:
                raise forms.ValidationError(
                    'صيغة الملف غير مدعومة. يرجى رفع ملف بصيغة .xlsx أو .xls'
                )
            
            # Check file size (50MB max)
            if file.size > 52428800:
                raise forms.ValidationError(
                    'حجم الملف كبير جداً. الحد الأقصى هو 50 ميجابايت'
                )
            
            # Check if file is not empty
            if file.size == 0:
                raise forms.ValidationError('الملف فارغ. يرجى رفع ملف يحتوي على بيانات')
        
        return file
