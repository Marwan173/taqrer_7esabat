import json
import os
import traceback

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib import messages

from .models import UploadedFile, AnalysisResult
from .forms import ExcelUploadForm
from .analysis_engine import DataAnalyzer


def upload_view(request):
    """Handle file upload page and form submission."""
    if request.method == 'POST':
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file_obj = request.FILES['file']
            
            # Create the UploadedFile record
            upload = UploadedFile.objects.create(
                file=uploaded_file_obj,
                original_filename=uploaded_file_obj.name,
                file_size=uploaded_file_obj.size,
                status='processing'
            )
            
            try:
                analysis_mode = request.POST.get('analysis_mode', 'auto')
                custom_query = request.POST.get('custom_query', '').strip()
                
                # Run analysis based on selected mode
                analyzer = DataAnalyzer(upload.file.path)
                if analysis_mode == 'custom':
                    result = analyzer.run_custom_analysis(custom_query)
                else:
                    result = analyzer.run_full_analysis()
                
                if result['success']:
                    # Store analysis result
                    AnalysisResult.objects.create(
                        uploaded_file=upload,
                        analysis_mode=analysis_mode,
                        custom_query=custom_query,
                        result_data=result,
                        column_types=result.get('column_types', {}),
                        row_count=result.get('row_count', 0),
                        col_count=result.get('col_count', 0),
                        sheet_name=result.get('sheet_name', ''),
                    )
                    upload.status = 'completed'
                    upload.save()
                    
                    # For AJAX requests, return JSON
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'redirect_url': f'/analyzer/dashboard/{upload.pk}/'
                        })
                    
                    return redirect('dashboard', pk=upload.pk)
                else:
                    upload.status = 'error'
                    error_msg = result.get('error', 'حدث خطأ أثناء تحليل الملف')
                    
                    # Format column suggestions if query had no matches
                    if result.get('suggestions'):
                        sug_str = '، '.join([f'"{c}"' for c in result['suggestions']])
                        error_msg = f'لم يتم العثور على أعمدة تطابق طلبك "{custom_query}". هل تقصد أحد الأعمدة التالية الموجودة بالملف: [{sug_str}]؟'
                    
                    upload.error_message = error_msg
                    upload.save()
                    
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'success': False, 'error': error_msg})
                    
                    messages.error(request, error_msg)
                    
            except Exception as e:
                upload.status = 'error'
                upload.error_message = str(e)
                upload.save()
                error_msg = f'خطأ في معالجة الملف: {str(e)}'
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg})
                
                messages.error(request, error_msg)
        else:
            # Form validation errors
            errors = '; '.join([e for errors in form.errors.values() for e in errors])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': errors})
            messages.error(request, errors)
    else:
        form = ExcelUploadForm()
    
    # Get recent uploads for the sidebar
    recent_uploads = UploadedFile.objects.all()[:10]
    
    return render(request, 'analyzer/upload.html', {
        'form': form,
        'recent_uploads': recent_uploads,
    })


def dashboard_view(request, pk):
    """Render the dashboard page for a specific analysis."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    return render(request, 'analyzer/dashboard.html', {
        'upload': upload,
        'analysis': analysis,
        'analysis_id': pk,
    })


def insights_view(request, pk):
    """Render the detailed insights page."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    return render(request, 'analyzer/insights.html', {
        'upload': upload,
        'analysis': analysis,
        'analysis_id': pk,
    })


def history_view(request):
    """Show upload history."""
    uploads = UploadedFile.objects.all()
    return render(request, 'analyzer/history.html', {
        'uploads': uploads,
    })


# ---- API Endpoints ----

@require_GET
def api_analysis(request, pk):
    """Return full analysis data as JSON."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    # Check if filters are applied
    has_filters = any([
        request.GET.get('date_from'),
        request.GET.get('date_to'),
        request.GET.get('category'),
    ])
    
    if has_filters:
        # Re-run analysis with filters
        analyzer = DataAnalyzer(upload.file.path)
        filters_dict = {
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'category': request.GET.get('category', ''),
            'category_column': request.GET.get('category_column', ''),
        }
        result = analyzer.run_filtered_analysis(filters_dict)
        result['analysis_mode'] = analysis.analysis_mode
        result['custom_query'] = analysis.custom_query
        return JsonResponse(result)
    
    data = dict(analysis.result_data)
    data['analysis_mode'] = analysis.analysis_mode
    data['custom_query'] = analysis.custom_query
    return JsonResponse(data)


@require_GET
def api_charts(request, pk):
    """Return chart configurations as JSON."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    has_filters = any([
        request.GET.get('date_from'),
        request.GET.get('date_to'),
        request.GET.get('category'),
    ])
    
    if has_filters:
        analyzer = DataAnalyzer(upload.file.path)
        filters_dict = {
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'category': request.GET.get('category', ''),
            'category_column': request.GET.get('category_column', ''),
        }
        result = analyzer.run_filtered_analysis(filters_dict)
        return JsonResponse({'charts': result.get('charts', [])}, safe=False)
    
    return JsonResponse({'charts': analysis.result_data.get('charts', [])}, safe=False)


@require_GET
def api_kpis(request, pk):
    """Return KPI data as JSON."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    has_filters = any([
        request.GET.get('date_from'),
        request.GET.get('date_to'),
        request.GET.get('category'),
    ])
    
    if has_filters:
        analyzer = DataAnalyzer(upload.file.path)
        filters_dict = {
            'date_from': request.GET.get('date_from', ''),
            'date_to': request.GET.get('date_to', ''),
            'category': request.GET.get('category', ''),
            'category_column': request.GET.get('category_column', ''),
        }
        result = analyzer.run_filtered_analysis(filters_dict)
        return JsonResponse({'kpis': result.get('kpis', [])}, safe=False)
    
    return JsonResponse({'kpis': analysis.result_data.get('kpis', [])}, safe=False)


@require_GET
def api_insights(request, pk):
    """Return insights data as JSON."""
    upload = get_object_or_404(UploadedFile, pk=pk, status='completed')
    analysis = get_object_or_404(AnalysisResult, uploaded_file=upload)
    
    data = analysis.result_data
    return JsonResponse({
        'insights': data.get('insights', []),
        'trends': data.get('trends', []),
        'quality': data.get('quality', {}),
        'narrative': data.get('narrative', ''),
    })
