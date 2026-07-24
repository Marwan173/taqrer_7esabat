"""
Core data analysis engine.
Performs professional-grade analysis on Excel data including:
- Column type detection
- Data quality assessment
- KPI generation
- Chart recommendation
- Trend detection
- Arabic narrative generation
- Actionable insights
"""
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
import traceback
import re


class DataAnalyzer:
    """Professional data analysis engine that processes Excel files."""
    
    # Arabic month names for narrative
    ARABIC_MONTHS = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None
        self.original_df = None
        self.sheet_name = ''
        self.column_types = {}  # {col_name: 'numeric'|'categorical'|'datetime'|'text'}
        self.numeric_cols = []
        self.categorical_cols = []
        self.datetime_cols = []
        self.text_cols = []
        
    def load_data(self):
        """Load Excel file and select the best sheet to analyze."""
        try:
            # Try openpyxl first, fall back to xlrd
            excel_file = None
            try:
                excel_file = pd.ExcelFile(self.file_path, engine='openpyxl')
            except Exception:
                excel_file = pd.ExcelFile(self.file_path, engine='xlrd')
            
            with excel_file as xls:
                # Find the first non-empty sheet
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if not df.empty and len(df.columns) > 0:
                        self.df = df
                        self.original_df = df.copy()
                        self.sheet_name = sheet
                        break
            
            if self.df is None:
                raise ValueError('جميع الأوراق في الملف فارغة')
            
            # Clean column names
            self.df.columns = [str(col).strip() for col in self.df.columns]
            
            # Drop completely empty rows and columns
            self.df.dropna(how='all', inplace=True)
            self.df.dropna(axis=1, how='all', inplace=True)
            
            if self.df.empty:
                raise ValueError('الملف لا يحتوي على بيانات صالحة')
                
            return True
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'خطأ في قراءة الملف: {str(e)}')
    
    def detect_column_types(self):
        """Detect the type of each column using smart heuristics."""
        for col in self.df.columns:
            series = self.df[col].dropna()
            if len(series) == 0:
                self.column_types[col] = 'text'
                self.text_cols.append(col)
                continue
            
            # Check for datetime
            if pd.api.types.is_datetime64_any_dtype(series):
                self.column_types[col] = 'datetime'
                self.datetime_cols.append(col)
                continue
            
            # Try to parse as datetime
            if series.dtype == object:
                try:
                    parsed = pd.to_datetime(series, infer_datetime_format=True, errors='coerce')
                    if parsed.notna().sum() / len(series) > 0.7:
                        self.df[col] = parsed
                        self.column_types[col] = 'datetime'
                        self.datetime_cols.append(col)
                        continue
                except Exception:
                    pass
            
            # Check for numeric
            if pd.api.types.is_numeric_dtype(series):
                # If numeric but very few unique values relative to total, might be categorical
                unique_ratio = series.nunique() / len(series)
                if series.nunique() <= 10 and unique_ratio < 0.05:
                    self.column_types[col] = 'categorical'
                    self.categorical_cols.append(col)
                else:
                    self.column_types[col] = 'numeric'
                    self.numeric_cols.append(col)
                continue
            
            # Try converting string to numeric
            if series.dtype == object:
                try:
                    numeric_series = pd.to_numeric(series.str.replace(',', '').str.replace('٬', ''), errors='coerce')
                    if numeric_series.notna().sum() / len(series) > 0.7:
                        self.df[col] = numeric_series
                        self.column_types[col] = 'numeric'
                        self.numeric_cols.append(col)
                        continue
                except Exception:
                    pass
            
            # Categorical vs text: low cardinality = categorical
            if series.dtype == object:
                unique_count = series.nunique()
                if unique_count <= 30 and (unique_count / len(series)) < 0.5:
                    self.column_types[col] = 'categorical'
                    self.categorical_cols.append(col)
                else:
                    self.column_types[col] = 'text'
                    self.text_cols.append(col)
            else:
                self.column_types[col] = 'text'
                self.text_cols.append(col)
    
    def assess_data_quality(self):
        """Assess data quality and return issues found."""
        issues = []
        details = {}
        total_cells = self.df.shape[0] * self.df.shape[1]
        
        # Missing values
        missing = self.df.isnull().sum()
        missing_cols = missing[missing > 0]
        total_missing = int(missing_cols.sum())
        if total_missing > 0:
            missing_pct = round(total_missing / total_cells * 100, 1)
            issues.append({
                'type': 'missing',
                'severity': 'warning' if missing_pct < 10 else 'danger',
                'message': f'يوجد {total_missing} قيمة مفقودة ({missing_pct}% من البيانات)',
                'icon': 'exclamation-triangle'
            })
            details['missing_by_column'] = {
                col: {'count': int(count), 'percentage': round(count / len(self.df) * 100, 1)}
                for col, count in missing_cols.items()
            }
        
        # Duplicate rows
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            dup_pct = round(dup_count / len(self.df) * 100, 1)
            issues.append({
                'type': 'duplicates',
                'severity': 'warning',
                'message': f'يوجد {dup_count} صف مكرر ({dup_pct}% من الصفوف)',
                'icon': 'copy'
            })
            details['duplicate_count'] = dup_count
        
        # Outliers in numeric columns
        outlier_info = {}
        for col in self.numeric_cols:
            series = self.df[col].dropna()
            if len(series) < 10:
                continue
            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            if IQR == 0:
                continue
            outliers = ((series < Q1 - 1.5 * IQR) | (series > Q3 + 1.5 * IQR)).sum()
            if outliers > 0:
                outlier_info[col] = int(outliers)
        
        if outlier_info:
            total_outliers = sum(outlier_info.values())
            issues.append({
                'type': 'outliers',
                'severity': 'info',
                'message': f'تم اكتشاف {total_outliers} قيمة شاذة في {len(outlier_info)} عمود',
                'icon': 'chart-line'
            })
            details['outliers_by_column'] = outlier_info
        
        # Data completeness score
        completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100
        
        if not issues:
            issues.append({
                'type': 'clean',
                'severity': 'success',
                'message': 'جودة البيانات ممتازة — لم يتم اكتشاف مشاكل',
                'icon': 'check-circle'
            })
        
        return {
            'issues': issues,
            'details': details,
            'completeness_score': completeness,
            'total_rows': len(self.df),
            'total_columns': len(self.df.columns)
        }
    
    def generate_kpis(self):
        """Generate smart KPI cards from the data."""
        kpis = []
        
        # For each numeric column, generate meaningful KPIs
        # Prioritize columns that look like financial/business metrics
        priority_keywords = ['مبيعات', 'إيرادات', 'ربح', 'تكلفة', 'سعر', 'كمية', 'عدد',
                           'sales', 'revenue', 'profit', 'cost', 'price', 'quantity', 'amount',
                           'total', 'count', 'المبلغ', 'القيمة', 'الإجمالي']
        
        scored_cols = []
        for col in self.numeric_cols:
            score = 0
            col_lower = col.lower()
            for kw in priority_keywords:
                if kw in col_lower:
                    score += 10
            # Higher variance = more interesting
            series = self.df[col].dropna()
            if len(series) > 0 and series.std() > 0:
                cv = series.std() / abs(series.mean()) if series.mean() != 0 else 0
                score += min(cv * 5, 10)
            scored_cols.append((col, score))
        
        scored_cols.sort(key=lambda x: x[1], reverse=True)
        top_numeric = [col for col, _ in scored_cols[:4]]
        
        for col in top_numeric:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            
            total = float(series.sum())
            mean = float(series.mean())
            
            # Calculate trend if datetime column exists
            trend = None
            trend_value = 0
            if self.datetime_cols:
                dt_col = self.datetime_cols[0]
                try:
                    temp_df = self.df[[dt_col, col]].dropna().sort_values(dt_col)
                    if len(temp_df) >= 4:
                        mid = len(temp_df) // 2
                        first_half = temp_df[col].iloc[:mid].mean()
                        second_half = temp_df[col].iloc[mid:].mean()
                        if first_half != 0:
                            trend_value = round((second_half - first_half) / abs(first_half) * 100, 1)
                            trend = 'up' if trend_value > 0 else 'down' if trend_value < 0 else 'stable'
                except Exception:
                    pass
            
            kpis.append({
                'label': f'إجمالي {col}',
                'value': self._format_number(total),
                'raw_value': total,
                'type': 'total',
                'icon': 'calculator',
                'trend': trend,
                'trend_value': trend_value,
                'color': 'primary'
            })
            
            kpis.append({
                'label': f'متوسط {col}',
                'value': self._format_number(mean),
                'raw_value': mean,
                'type': 'average',
                'icon': 'chart-bar',
                'trend': trend,
                'trend_value': trend_value,
                'color': 'info'
            })
        
        # Best/worst category KPI
        if self.categorical_cols and self.numeric_cols:
            cat_col = self.categorical_cols[0]
            num_col = top_numeric[0] if top_numeric else self.numeric_cols[0]
            try:
                grouped = self.df.groupby(cat_col)[num_col].sum().sort_values(ascending=False)
                if len(grouped) >= 2:
                    kpis.append({
                        'label': f'أعلى {cat_col}',
                        'value': str(grouped.index[0]),
                        'raw_value': float(grouped.iloc[0]),
                        'subtitle': self._format_number(float(grouped.iloc[0])),
                        'type': 'best',
                        'icon': 'trophy',
                        'trend': 'up',
                        'trend_value': 0,
                        'color': 'success'
                    })
                    kpis.append({
                        'label': f'أدنى {cat_col}',
                        'value': str(grouped.index[-1]),
                        'raw_value': float(grouped.iloc[-1]),
                        'subtitle': self._format_number(float(grouped.iloc[-1])),
                        'type': 'worst',
                        'icon': 'arrow-down',
                        'trend': 'down',
                        'trend_value': 0,
                        'color': 'danger'
                    })
            except Exception:
                pass
        
        # Row count KPI
        kpis.append({
            'label': 'عدد السجلات',
            'value': f"{len(self.df):,}",
            'raw_value': len(self.df),
            'type': 'count',
            'icon': 'database',
            'trend': None,
            'trend_value': 0,
            'color': 'secondary'
        })
        
        return kpis[:8]  # Limit to 8 KPIs
    
    def recommend_charts(self):
        """Recommend the best chart types based on data characteristics."""
        charts = []
        used_combos = set()
        
        # 1. Categorical + Numeric → Bar Chart
        if self.categorical_cols and self.numeric_cols:
            cat_col = self._best_categorical_col()
            num_col = self._best_numeric_col()
            combo_key = f'bar_{cat_col}_{num_col}'
            if combo_key not in used_combos:
                used_combos.add(combo_key)
                grouped = self.df.groupby(cat_col)[num_col].sum().sort_values(ascending=False).head(15)
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'bar',
                    'title': f'{num_col} حسب {cat_col}',
                    'data': {
                        'labels': [str(x) for x in grouped.index.tolist()],
                        'datasets': [{
                            'label': num_col,
                            'data': [round(float(x), 2) for x in grouped.values.tolist()],
                            'backgroundColor': self._get_color_palette(len(grouped)),
                            'borderRadius': 6,
                        }]
                    },
                    'priority': 10
                })
        
        # 2. DateTime + Numeric → Line Chart with Trendline
        if self.datetime_cols and self.numeric_cols:
            dt_col = self.datetime_cols[0]
            for num_col in self.numeric_cols[:2]:
                combo_key = f'line_{dt_col}_{num_col}'
                if combo_key not in used_combos:
                    used_combos.add(combo_key)
                    try:
                        temp = self.df[[dt_col, num_col]].dropna().sort_values(dt_col)
                        # Resample if too many points
                        if len(temp) > 100:
                            temp = temp.set_index(dt_col).resample('W').mean().reset_index()
                        elif len(temp) > 50:
                            temp = temp.set_index(dt_col).resample('D').mean().reset_index().dropna()
                        
                        labels = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in temp[dt_col]]
                        values = [round(float(x), 2) if pd.notna(x) else None for x in temp[num_col]]
                        
                        # Calculate trendline
                        clean_vals = [(i, v) for i, v in enumerate(values) if v is not None]
                        trendline = None
                        if len(clean_vals) >= 3:
                            x_arr = np.array([p[0] for p in clean_vals])
                            y_arr = np.array([p[1] for p in clean_vals])
                            slope, intercept, _, _, _ = stats.linregress(x_arr, y_arr)
                            trendline = [round(float(slope * i + intercept), 2) for i in range(len(values))]
                        
                        dataset = {
                            'label': num_col,
                            'data': values,
                            'borderColor': '#4f46e5',
                            'backgroundColor': 'rgba(79, 70, 229, 0.1)',
                            'fill': True,
                            'tension': 0.4,
                            'pointRadius': 2,
                        }
                        datasets = [dataset]
                        if trendline:
                            datasets.append({
                                'label': 'خط الاتجاه',
                                'data': trendline,
                                'borderColor': '#ef4444',
                                'borderDash': [5, 5],
                                'fill': False,
                                'pointRadius': 0,
                                'borderWidth': 2,
                            })
                        
                        charts.append({
                            'id': f'chart_{len(charts)}',
                            'type': 'line',
                            'title': f'اتجاه {num_col} عبر الزمن',
                            'data': {
                                'labels': labels,
                                'datasets': datasets
                            },
                            'priority': 9
                        })
                    except Exception:
                        pass
        
        # 3. Categorical proportions → Donut Chart
        if self.categorical_cols:
            cat_col = self._best_categorical_col()
            value_counts = self.df[cat_col].value_counts().head(8)
            if len(value_counts) >= 2:
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'doughnut',
                    'title': f'توزيع {cat_col}',
                    'data': {
                        'labels': [str(x) for x in value_counts.index.tolist()],
                        'datasets': [{
                            'data': [int(x) for x in value_counts.values.tolist()],
                            'backgroundColor': self._get_color_palette(len(value_counts)),
                            'borderWidth': 2,
                            'borderColor': '#ffffff',
                        }]
                    },
                    'priority': 7
                })
        
        # 4. Two numeric columns → Scatter Plot
        if len(self.numeric_cols) >= 2:
            col1, col2 = self.numeric_cols[0], self.numeric_cols[1]
            combo_key = f'scatter_{col1}_{col2}'
            if combo_key not in used_combos:
                used_combos.add(combo_key)
                temp = self.df[[col1, col2]].dropna()
                if len(temp) > 500:
                    temp = temp.sample(500, random_state=42)
                
                # Calculate correlation
                corr = temp[col1].corr(temp[col2])
                corr_text = ''
                if abs(corr) > 0.7:
                    corr_text = ' (ارتباط قوي)'
                elif abs(corr) > 0.4:
                    corr_text = ' (ارتباط متوسط)'
                
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'scatter',
                    'title': f'العلاقة بين {col1} و {col2}{corr_text}',
                    'data': {
                        'datasets': [{
                            'label': f'{col1} مقابل {col2}',
                            'data': [{'x': round(float(row[col1]), 2), 'y': round(float(row[col2]), 2)} for _, row in temp.iterrows()],
                            'backgroundColor': 'rgba(79, 70, 229, 0.5)',
                            'pointRadius': 4,
                        }]
                    },
                    'correlation': round(float(corr), 3) if pd.notna(corr) else None,
                    'priority': 6
                })
        
        # 5. Numeric distribution → Histogram (as bar chart)
        if self.numeric_cols:
            num_col = self._best_numeric_col()
            series = self.df[num_col].dropna()
            if len(series) >= 10:
                hist_values, bin_edges = np.histogram(series, bins=min(20, max(5, len(series) // 10)))
                bin_labels = [f"{round(float(bin_edges[i]), 1)}-{round(float(bin_edges[i+1]), 1)}" for i in range(len(hist_values))]
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'bar',
                    'title': f'توزيع {num_col}',
                    'data': {
                        'labels': bin_labels,
                        'datasets': [{
                            'label': 'التكرار',
                            'data': [int(x) for x in hist_values.tolist()],
                            'backgroundColor': 'rgba(16, 185, 129, 0.7)',
                            'borderColor': '#10b981',
                            'borderWidth': 1,
                            'borderRadius': 4,
                        }]
                    },
                    'priority': 5
                })
        
        # 6. If multiple categorical + numeric: stacked/grouped bar
        if len(self.categorical_cols) >= 2 and self.numeric_cols:
            cat1 = self.categorical_cols[0]
            cat2 = self.categorical_cols[1]
            num_col = self._best_numeric_col()
            try:
                pivot = self.df.pivot_table(index=cat1, columns=cat2, values=num_col, aggfunc='sum').fillna(0)
                if pivot.shape[0] <= 15 and pivot.shape[1] <= 8:
                    colors = self._get_color_palette(pivot.shape[1])
                    datasets = []
                    for i, cat2_val in enumerate(pivot.columns):
                        datasets.append({
                            'label': str(cat2_val),
                            'data': [round(float(x), 2) for x in pivot[cat2_val].values.tolist()],
                            'backgroundColor': colors[i % len(colors)],
                            'borderRadius': 4,
                        })
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'bar',
                        'title': f'{num_col} حسب {cat1} و {cat2}',
                        'data': {
                            'labels': [str(x) for x in pivot.index.tolist()],
                            'datasets': datasets
                        },
                        'options': {'stacked': True},
                        'priority': 5
                    })
            except Exception:
                pass
        
        # Sort by priority and limit
        charts.sort(key=lambda x: x.get('priority', 0), reverse=True)
        return charts[:8]
    
    def detect_trends(self):
        """Detect significant trends and patterns in the data."""
        trends = []
        
        # Time-series trends
        if self.datetime_cols and self.numeric_cols:
            dt_col = self.datetime_cols[0]
            for num_col in self.numeric_cols[:3]:
                try:
                    temp = self.df[[dt_col, num_col]].dropna().sort_values(dt_col)
                    if len(temp) < 5:
                        continue
                    
                    # Overall trend
                    x = np.arange(len(temp))
                    y = temp[num_col].values.astype(float)
                    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                    
                    if p_value < 0.05:  # Statistically significant
                        first_val = y[0] if y[0] != 0 else 1
                        pct_change = round((y[-1] - y[0]) / abs(first_val) * 100, 1)
                        direction = 'ارتفاع' if slope > 0 else 'انخفاض'
                        trends.append({
                            'type': 'trend',
                            'column': num_col,
                            'direction': 'up' if slope > 0 else 'down',
                            'message': f'{direction} في {num_col} بنسبة {abs(pct_change)}% خلال الفترة المحللة',
                            'r_squared': round(float(r_value ** 2), 3),
                            'significance': 'high' if p_value < 0.01 else 'medium'
                        })
                    
                    # Detect recent spike or drop (last 10% vs previous)
                    n = len(y)
                    if n >= 10:
                        recent = y[int(n * 0.9):]
                        previous = y[:int(n * 0.9)]
                        recent_mean = np.mean(recent)
                        prev_mean = np.mean(previous)
                        if prev_mean != 0:
                            change = (recent_mean - prev_mean) / abs(prev_mean) * 100
                            if abs(change) > 20:
                                trends.append({
                                    'type': 'spike' if change > 0 else 'drop',
                                    'column': num_col,
                                    'direction': 'up' if change > 0 else 'down',
                                    'message': f'تغير ملحوظ في {num_col} مؤخراً: {"ارتفاع" if change > 0 else "انخفاض"} بنسبة {abs(round(change, 1))}%',
                                    'significance': 'high'
                                })
                except Exception:
                    continue
        
        # Top/Bottom performers
        if self.categorical_cols and self.numeric_cols:
            cat_col = self._best_categorical_col()
            num_col = self._best_numeric_col()
            try:
                grouped = self.df.groupby(cat_col)[num_col].sum().sort_values(ascending=False)
                if len(grouped) >= 3:
                    top = grouped.head(3)
                    total = grouped.sum()
                    if total > 0:
                        top_pct = round(top.sum() / total * 100, 1)
                        top_names = '، '.join([str(x) for x in top.index[:3]])
                        trends.append({
                            'type': 'concentration',
                            'column': cat_col,
                            'direction': 'neutral',
                            'message': f'أعلى 3 فئات ({top_names}) تمثل {top_pct}% من إجمالي {num_col}',
                            'significance': 'high' if top_pct > 60 else 'medium'
                        })
            except Exception:
                pass
        
        # Correlation insights
        if len(self.numeric_cols) >= 2:
            for i in range(min(len(self.numeric_cols), 5)):
                for j in range(i + 1, min(len(self.numeric_cols), 5)):
                    col1, col2 = self.numeric_cols[i], self.numeric_cols[j]
                    try:
                        corr = self.df[col1].corr(self.df[col2])
                        if pd.notna(corr) and abs(corr) > 0.7:
                            direction = 'طردي' if corr > 0 else 'عكسي'
                            trends.append({
                                'type': 'correlation',
                                'column': f'{col1} & {col2}',
                                'direction': 'up' if corr > 0 else 'down',
                                'message': f'ارتباط {direction} قوي ({round(abs(corr), 2)}) بين {col1} و {col2}',
                                'significance': 'high' if abs(corr) > 0.85 else 'medium'
                            })
                    except Exception:
                        pass
        
        return trends
    
    def generate_narrative(self, kpis, trends, quality):
        """Generate an Arabic narrative summary (2-4 sentences)."""
        sentences = []
        
        # Opening sentence about the dataset
        rows = len(self.df)
        cols = len(self.df.columns)
        sentences.append(f'يحتوي مجموع البيانات على {rows:,} سجل عبر {cols} عمود.')
        
        # Key trend sentence
        significant_trends = [t for t in trends if t.get('significance') == 'high']
        if significant_trends:
            trend = significant_trends[0]
            sentences.append(trend['message'] + '.')
        
        # Top performer or concentration
        concentration = [t for t in trends if t['type'] == 'concentration']
        if concentration:
            sentences.append(concentration[0]['message'] + '.')
        
        # Data quality note if needed
        if quality['completeness_score'] < 90:
            sentences.append(
                f'ملاحظة: نسبة اكتمال البيانات {quality["completeness_score"]}% — يُنصح بمعالجة القيم المفقودة للحصول على نتائج أدق.'
            )
        
        # If we don't have enough sentences, add a general one
        if len(sentences) < 2:
            if self.numeric_cols:
                col = self.numeric_cols[0]
                total = self.df[col].sum()
                avg = self.df[col].mean()
                sentences.append(f'إجمالي {col} يبلغ {self._format_number(total)} بمتوسط {self._format_number(avg)}.')
        
        return ' '.join(sentences[:4])
    
    def generate_insights(self, trends, quality):
        """Generate actionable insights and recommendations in Arabic."""
        insights = []
        
        # Insights from trends
        for trend in trends:
            if trend['type'] == 'trend' and trend['direction'] == 'up':
                insights.append({
                    'category': 'فرصة',
                    'icon': 'lightbulb',
                    'color': 'success',
                    'title': f'نمو في {trend["column"]}',
                    'description': trend['message'] + '. استمر في تعزيز العوامل المساهمة في هذا النمو.',
                    'priority': 'high'
                })
            elif trend['type'] == 'trend' and trend['direction'] == 'down':
                insights.append({
                    'category': 'تحذير',
                    'icon': 'exclamation-circle',
                    'color': 'danger',
                    'title': f'تراجع في {trend["column"]}',
                    'description': trend['message'] + '. يُنصح بتحليل أسباب هذا التراجع واتخاذ إجراءات تصحيحية.',
                    'priority': 'high'
                })
            elif trend['type'] == 'concentration':
                insights.append({
                    'category': 'ملاحظة',
                    'icon': 'info-circle',
                    'color': 'info',
                    'title': 'تركز عالي في فئات محددة',
                    'description': trend['message'] + '. قد يشير هذا إلى اعتماد كبير على فئات محدودة — فكر في التنويع.',
                    'priority': 'medium'
                })
            elif trend['type'] == 'correlation':
                insights.append({
                    'category': 'اكتشاف',
                    'icon': 'link',
                    'color': 'primary',
                    'title': f'علاقة بين {trend["column"]}',
                    'description': trend['message'] + '. يمكن الاستفادة من هذه العلاقة في التنبؤ والتخطيط.',
                    'priority': 'medium'
                })
            elif trend['type'] in ('spike', 'drop'):
                insights.append({
                    'category': 'تنبيه',
                    'icon': 'bolt',
                    'color': 'warning',
                    'title': f'تغير مفاجئ في {trend["column"]}',
                    'description': trend['message'] + '. تحقق من الأسباب وراء هذا التغير المفاجئ.',
                    'priority': 'high'
                })
        
        # Data quality insights
        for issue in quality.get('issues', []):
            if issue['type'] == 'missing':
                insights.append({
                    'category': 'جودة البيانات',
                    'icon': 'database',
                    'color': 'warning',
                    'title': 'بيانات مفقودة',
                    'description': issue['message'] + '. يُنصح بمعالجة هذه الفجوات لضمان دقة التحليل.',
                    'priority': 'medium'
                })
            elif issue['type'] == 'duplicates':
                insights.append({
                    'category': 'جودة البيانات',
                    'icon': 'copy',
                    'color': 'warning',
                    'title': 'صفوف مكررة',
                    'description': issue['message'] + '. قد تؤثر البيانات المكررة على دقة النتائج.',
                    'priority': 'medium'
                })
        
        # If no insights were generated, add a general one
        if not insights:
            insights.append({
                'category': 'ملاحظة',
                'icon': 'check-circle',
                'color': 'success',
                'title': 'بيانات مستقرة',
                'description': 'لم يتم اكتشاف أنماط غير عادية. البيانات تبدو مستقرة ومتسقة.',
                'priority': 'low'
            })
        
        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 3))
        
        return insights
    
    def run_full_analysis(self):
        """Run the complete analysis pipeline and return all results."""
        try:
            self.load_data()
            self.detect_column_types()
            
            quality = self.assess_data_quality()
            kpis = self.generate_kpis()
            charts = self.recommend_charts()
            trends = self.detect_trends()
            narrative = self.generate_narrative(kpis, trends, quality)
            insights = self.generate_insights(trends, quality)
            
            # Get available filter values
            filters = self._get_filter_options()
            
            return {
                'success': True,
                'sheet_name': self.sheet_name,
                'row_count': len(self.df),
                'col_count': len(self.df.columns),
                'column_types': self.column_types,
                'columns': list(self.df.columns),
                'narrative': narrative,
                'quality': quality,
                'kpis': kpis,
                'charts': charts,
                'trends': trends,
                'insights': insights,
                'filters': filters,
            }
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'خطأ غير متوقع أثناء التحليل: {str(e)}'}
    
    def run_filtered_analysis(self, filters_dict):
        """Re-run analysis with filters applied."""
        try:
            self.load_data()
            self.detect_column_types()
            
            # Apply date filters
            date_from = filters_dict.get('date_from')
            date_to = filters_dict.get('date_to')
            if self.datetime_cols and (date_from or date_to):
                dt_col = self.datetime_cols[0]
                if date_from:
                    try:
                        self.df = self.df[self.df[dt_col] >= pd.to_datetime(date_from)]
                    except Exception:
                        pass
                if date_to:
                    try:
                        self.df = self.df[self.df[dt_col] <= pd.to_datetime(date_to)]
                    except Exception:
                        pass
            
            # Apply category filter
            category = filters_dict.get('category')
            category_column = filters_dict.get('category_column')
            if category and category_column and category_column in self.categorical_cols:
                self.df = self.df[self.df[category_column].astype(str) == category]
            
            if self.df.empty:
                return {'success': False, 'error': 'لا توجد بيانات تطابق معايير التصفية المحددة'}
            
            # Re-detect types on filtered data
            self.numeric_cols = [c for c in self.numeric_cols if c in self.df.columns]
            self.categorical_cols = [c for c in self.categorical_cols if c in self.df.columns]
            self.datetime_cols = [c for c in self.datetime_cols if c in self.df.columns]
            
            quality = self.assess_data_quality()
            kpis = self.generate_kpis()
            charts = self.recommend_charts()
            trends = self.detect_trends()
            narrative = self.generate_narrative(kpis, trends, quality)
            insights = self.generate_insights(trends, quality)
            
            return {
                'success': True,
                'kpis': kpis,
                'charts': charts,
                'narrative': narrative,
                'trends': trends,
                'insights': insights,
                'quality': quality,
                'filtered_rows': len(self.df),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # ---- Helper Methods ----
    
    def _best_categorical_col(self):
        """Pick the most informative categorical column."""
        best = None
        best_score = -1
        for col in self.categorical_cols:
            n_unique = self.df[col].nunique()
            # Prefer columns with 3-15 unique values
            score = 10 - abs(n_unique - 8)
            if 3 <= n_unique <= 15:
                score += 5
            if score > best_score:
                best_score = score
                best = col
        return best or (self.categorical_cols[0] if self.categorical_cols else None)
    
    def _best_numeric_col(self):
        """Pick the most informative numeric column."""
        if not self.numeric_cols:
            return None
        best = None
        best_score = -1
        priority_keywords = ['مبيعات', 'إيرادات', 'ربح', 'تكلفة', 'سعر', 'كمية',
                           'sales', 'revenue', 'profit', 'cost', 'price', 'amount', 'total']
        for col in self.numeric_cols:
            score = 0
            col_lower = col.lower()
            for kw in priority_keywords:
                if kw in col_lower:
                    score += 10
            series = self.df[col].dropna()
            if len(series) > 0:
                if series.std() > 0:
                    score += 5
            if score > best_score:
                best_score = score
                best = col
        return best or self.numeric_cols[0]
    
    def _format_number(self, num):
        """Format a number for Arabic display."""
        if abs(num) >= 1_000_000_000:
            return f"{num/1_000_000_000:.1f} مليار"
        elif abs(num) >= 1_000_000:
            return f"{num/1_000_000:.1f} مليون"
        elif abs(num) >= 1_000:
            return f"{num:,.0f}"
        elif abs(num) >= 1:
            return f"{num:,.2f}"
        else:
            return f"{num:.4f}"
    
    def _get_color_palette(self, n):
        """Return a list of n colors for charts."""
        palette = [
            '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
            '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
            '#84cc16', '#e11d48', '#0891b2', '#a855f7', '#65a30d',
        ]
        return (palette * ((n // len(palette)) + 1))[:n]
    
    def _get_filter_options(self):
        """Get available filter options from the data."""
        filters = {}
        
        # Date range
        if self.datetime_cols:
            dt_col = self.datetime_cols[0]
            try:
                dates = self.df[dt_col].dropna()
                if len(dates) > 0:
                    filters['date'] = {
                        'column': dt_col,
                        'min': dates.min().strftime('%Y-%m-%d') if hasattr(dates.min(), 'strftime') else str(dates.min()),
                        'max': dates.max().strftime('%Y-%m-%d') if hasattr(dates.max(), 'strftime') else str(dates.max()),
                    }
            except Exception:
                pass
        
        # Categories
        if self.categorical_cols:
            filters['categories'] = {}
            for col in self.categorical_cols[:3]:
                values = self.df[col].dropna().unique().tolist()
                filters['categories'][col] = [str(v) for v in values[:50]]
        
        return filters
