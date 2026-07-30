"""
Core Data Analysis Engine — Value-Driven, Adaptive 5-Step Process.

Step 1: Multi-signal profiling (sample actual values, inspect dtypes, semantic roles, distribution shape, confidence)
Step 2: Content-driven adaptive storytelling (small datasets, categorical-heavy, temporal signal, part-to-whole limits)
Step 3: Non-templated dynamic dashboards (flexible KPI count 2–8, adaptive chart selections, business Arabic labels)
Step 4: Surface uncertainties & validate inferred meanings before action
Step 5: Specific Arabic narrative & headline insights based on empirical findings
"""
import pandas as pd
import numpy as np
from scipy import stats
import traceback
import re
import logging

from .ai_service import AIService

logger = logging.getLogger(__name__)


class DataAnalyzer:
    """Professional value-driven data analysis engine."""

    ARABIC_MONTHS = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }

    # Keyword sets for derived metric detection
    PRICE_KEYWORDS    = ['price', 'سعر', 'unit_price', 'سعر_وحدة', 'سعر الوحدة', 'تكلفة', 'cost', 'rate', 'معدل', 'سعر_البيع']
    QTY_KEYWORDS      = ['quantity', 'qty', 'كمية', 'عدد', 'units', 'وحدات', 'pieces', 'كميه', 'الكمية']
    REVENUE_KEYWORDS  = ['revenue', 'مبيعات', 'إيرادات', 'total', 'إجمالي', 'sales', 'amount', 'مبلغ', 'قيمة_المبيعات']
    START_KW          = ['start', 'begin', 'بداية', 'تاريخ_البداية', 'from', 'open', 'created', 'تاريخ_الفتح']
    END_KW            = ['end', 'close', 'نهاية', 'تاريخ_النهاية', 'to', 'finish', 'completed', 'closed', 'تاريخ_الاغلاق']

    # Known geographic indicators
    GEO_INDICATORS = {
        'الرياض', 'جدة', 'مكة', 'المدينة', 'الدمام', 'الخبر', 'الشارقة', 'دبي', 'أبوظبي', 'القاهرة', 'الإسكندرية',
        'مصر', 'السعودية', 'الإمارات', 'الكويت', 'قطر', 'عمان', 'البحرين', 'الاردن', 'لبنان',
        'riyadh', 'jeddah', 'mecca', 'medina', 'dammam', 'khobar', 'dubai', 'cairo', 'alexandria',
        'saudi', 'uae', 'egypt', 'kuwait', 'qatar', 'oman', 'bahrain', 'jordan', 'usa', 'uk', 'london', 'new york'
    }

    # Status / state value indicators
    STATUS_INDICATORS = {
        'مكتمل', 'قيد المعالجة', 'قيد الانتظار', 'ملغى', 'مرفوض', 'تم', 'ناجح', 'فاشل', 'نشط', 'غير نشط',
        'active', 'inactive', 'pending', 'completed', 'cancelled', 'rejected', 'approved', 'done',
        'passed', 'failed', 'open', 'closed', 'in_progress', 'draft', 'published'
    }

    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None
        self.original_df = None
        self.sheet_name = ''

        # Step 1: Column profiles with rich semantic data
        self.column_profiles = {}

        # Categorized column lists
        self.measure_cols    = []   # role='measure'
        self.dimension_cols  = []   # role='dimension'
        self.datetime_cols   = []   # role='datetime'
        self.key_cols        = []   # role='key'
        self.text_cols       = []   # role='text'

        # Aliases for backward compatibility
        self.numeric_cols     = []
        self.categorical_cols = []
        self.column_types     = {}

        # Step 2: Derived metrics
        self.derived_metrics = []

        # Outliers & Anomalies detected
        self.anomalies = []

    # =========================================================
    # DATA LOADING
    # =========================================================

    def load_data(self):
        """Load Excel file and select best sheet."""
        try:
            excel_file = None
            try:
                ext = str(self.file_path).lower().rsplit('.', 1)[-1]
                engine = 'xlrd' if ext == 'xls' else 'openpyxl'
                excel_file = pd.ExcelFile(self.file_path, engine=engine)
            except Exception:
                excel_file = pd.ExcelFile(self.file_path, engine='xlrd')

            with excel_file as xls:
                for sheet in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if not df.empty and len(df.columns) > 0:
                        self.df = df
                        self.original_df = df.copy()
                        self.sheet_name = sheet
                        break

            if self.df is None:
                raise ValueError('جميع الأوراق في الملف فارغة')

            self.df.columns = [str(col).strip() for col in self.df.columns]
            self.df.dropna(how='all', inplace=True)
            self.df.dropna(axis=1, how='all', inplace=True)

            if self.df.empty:
                raise ValueError('الملف لا يحتوي على بيانات صالحة')

            return True
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f'خطأ في قراءة الملف: {str(e)}')

    # =========================================================
    # STEP 1 — MULTI-SIGNAL VALUE-BASED COLUMN PROFILER
    # =========================================================

    def profile_columns(self):
        """
        Step 1: Inspect actual values (not just headers) to infer:
          - True data type & semantic role (currency, rating, status, geo, phone, id, pct, flag, text, measure)
          - Distribution shape (skewness, variance, dominant values)
          - Inference confidence (high / medium / low)
        """
        n_rows = len(self.df)

        for col in self.df.columns:
            series = self.df[col]
            non_null = series.dropna()
            n_non_null = len(non_null)
            missing_count = int(series.isnull().sum())
            missing_pct = round(missing_count / n_rows * 100, 1) if n_rows > 0 else 0

            profile = {
                'col': col,
                'missing_count': missing_count,
                'missing_pct': missing_pct,
                'n_unique': int(non_null.nunique()) if n_non_null > 0 else 0,
                'cardinality_ratio': round(non_null.nunique() / n_non_null, 3) if n_non_null > 0 else 0,
                'all_same': False,
                'dtype': 'text',
                'role': 'text',
                'semantic_tag': 'general',
                'confidence': 'high',
                'uncertainty_note': None,
                'coerced': False,
                'mixed_format': False,
                'skewness': 0.0,
                'dominant_pct': 0.0,
            }

            if n_non_null == 0:
                profile['dtype'] = 'empty'
                profile['role'] = 'text'
                self.column_profiles[col] = profile
                self.text_cols.append(col)
                self.column_types[col] = 'text'
                continue

            if non_null.nunique() <= 1:
                profile['all_same'] = True

            # Calculate dominant value %
            if n_non_null > 0:
                top_freq = non_null.value_counts().iloc[0]
                profile['dominant_pct'] = round(top_freq / n_non_null * 100, 1)

            # ── 1. Datetime Check ──
            if pd.api.types.is_datetime64_any_dtype(series):
                profile['dtype'] = 'datetime'
                profile['role'] = 'datetime'
                profile['semantic_tag'] = 'date'
                self.column_profiles[col] = profile
                self.datetime_cols.append(col)
                self.column_types[col] = 'datetime'
                continue

            if series.dtype == object:
                try:
                    parsed = pd.to_datetime(non_null, infer_datetime_format=True, errors='coerce')
                    parse_rate = parsed.notna().sum() / len(non_null)
                    if parse_rate > 0.75:
                        self.df[col] = pd.to_datetime(series, infer_datetime_format=True, errors='coerce')
                        profile['dtype'] = 'datetime'
                        profile['role'] = 'datetime'
                        profile['semantic_tag'] = 'date'
                        profile['coerced'] = True
                        profile['confidence'] = 'high' if parse_rate > 0.95 else 'medium'
                        self.column_profiles[col] = profile
                        self.datetime_cols.append(col)
                        self.column_types[col] = 'datetime'
                        continue
                except Exception:
                    pass
            # ── 2. Value Pattern & Numeric Coercion Check ──
            raw_sample = non_null.astype(str).str.strip().head(100)
            is_phone_pattern = (raw_sample.str.match(r'^(05|5|\+?966|00966|\+?20|01)[0-9]{8,11}$').mean() > 0.6)

            is_numeric = pd.api.types.is_numeric_dtype(series)
            coerce_rate = 0.0

            if not is_numeric and series.dtype == object and not is_phone_pattern:
                try:
                    cleaned = non_null.astype(str).str.replace(r'[,،٬\s%]', '', regex=True)
                    coerced = pd.to_numeric(cleaned, errors='coerce')
                    coerce_rate = coerced.notna().sum() / len(non_null)
                    if coerce_rate > 0.75:
                        is_numeric = True
                        full_cleaned = series.astype(str).str.replace(r'[,،٬\s%]', '', regex=True)
                        self.df[col] = pd.to_numeric(full_cleaned, errors='coerce')
                        profile['coerced'] = True
                        profile['confidence'] = 'high' if coerce_rate > 0.95 else 'medium'
                    elif coerce_rate > 0.3:
                        profile['mixed_format'] = True
                        profile['confidence'] = 'low'
                        profile['uncertainty_note'] = f"يحتوي العمود '{col}' على مزيج من أرقام ونصوص تم التعامل معه كنص."
                except Exception:
                    pass

            # ── 3. Semantic Role Classification ──
            if is_phone_pattern:
                profile['dtype'] = 'text'
                profile['role'] = 'key'
                profile['semantic_tag'] = 'phone'
                self.key_cols.append(col)
                self.column_types[col] = 'text'
                self.column_profiles[col] = profile
                continue

            if is_numeric:
                num_series = self.df[col].dropna()
                n_unique_num = int(num_series.nunique())
                card_ratio = n_unique_num / len(num_series) if len(num_series) > 0 else 0

                profile['n_unique'] = n_unique_num
                profile['cardinality_ratio'] = round(card_ratio, 3)
                profile['dtype'] = 'numeric'

                if len(num_series) > 3:
                    try:
                        profile['skewness'] = round(float(stats.skew(num_series)), 2)
                    except Exception:
                        pass

                is_sequential_id = (
                    card_ratio > 0.95 and
                    num_series.min() >= 1 and
                    num_series.max() <= len(self.df) + 10 and
                    (num_series.diff().dropna() == 1).mean() > 0.8
                )

                col_lower = col.lower()
                id_keywords = ['id', 'رقم', 'code', 'كود', 'رمز', '#', 'num', 'seq', 'no', 'number', 'index', 'معرف']
                has_id_kw = any(kw in col_lower for kw in id_keywords)

                if is_sequential_id or (card_ratio > 0.8 and has_id_kw):
                    profile['role'] = 'key'
                    profile['semantic_tag'] = 'identifier'
                    self.key_cols.append(col)
                    self.column_types[col] = 'numeric'
                    if not has_id_kw and is_sequential_id:
                        profile['confidence'] = 'medium'
                        profile['uncertainty_note'] = f"تم تصنيف '{col}' كعمود تسلسلي (مفتاح) بناءً على النمط المتتابع للقيم."
                elif n_unique_num == 2:
                    # Boolean flag stored as 0/1
                    profile['role'] = 'dimension'
                    profile['semantic_tag'] = 'boolean'
                    self.dimension_cols.append(col)
                    self.categorical_cols.append(col)
                    self.column_types[col] = 'categorical'
                elif n_unique_num <= 15 and card_ratio < 0.05:
                    # Low cardinality numeric → dimension (e.g. rating 1–5, score, month 1–12)
                    profile['role'] = 'dimension'
                    profile['semantic_tag'] = 'rating' if num_series.min() >= 1 and num_series.max() <= 10 else 'bounded_score'
                    self.dimension_cols.append(col)
                    self.categorical_cols.append(col)
                    self.column_types[col] = 'categorical'
                else:
                    profile['role'] = 'measure'
                    # Sub-tag currency vs quantity vs general measure
                    if any(kw in col_lower for kw in self.PRICE_KEYWORDS + self.REVENUE_KEYWORDS):
                        profile['semantic_tag'] = 'currency'
                    elif any(kw in col_lower for kw in self.QTY_KEYWORDS):
                        profile['semantic_tag'] = 'quantity'
                    else:
                        profile['semantic_tag'] = 'measure'

                    self.measure_cols.append(col)
                    self.numeric_cols.append(col)
                    self.column_types[col] = 'numeric'

                self.column_profiles[col] = profile
                continue

            # ── 4. Categorical vs Text Value Inspection ──
            sample_vals = non_null.astype(str).head(200)
            sample_lower = sample_vals.str.lower().str.strip()

            n_unique_str = int(non_null.nunique())
            card_ratio = n_unique_str / n_non_null
            profile['n_unique'] = n_unique_str
            profile['cardinality_ratio'] = round(card_ratio, 3)

            col_lower = col.lower()

            # Check value patterns for Geo, Status, Boolean, ID
            is_geo = any(val in self.GEO_INDICATORS for val in sample_lower)
            is_status = any(val in self.STATUS_INDICATORS for val in sample_lower)
            is_bool = (n_unique_str == 2) or set(sample_lower.unique()).issubset({'yes', 'no', 'y', 'n', 'true', 'false', 'نعم', 'لا'})
            is_id_kw = any(kw in col_lower for kw in ['id', 'رقم', 'code', 'كود', 'رمز', 'no.', '#', 'num', 'email', 'phone', 'هاتف', 'بريد'])

            if is_bool:
                profile['dtype'] = 'categorical'
                profile['role'] = 'dimension'
                profile['semantic_tag'] = 'boolean'
                self.dimension_cols.append(col)
                self.categorical_cols.append(col)
                self.column_types[col] = 'categorical'
            elif is_geo:
                profile['dtype'] = 'categorical'
                profile['role'] = 'dimension'
                profile['semantic_tag'] = 'geography'
                self.dimension_cols.append(col)
                self.categorical_cols.append(col)
                self.column_types[col] = 'categorical'
            elif is_status:
                profile['dtype'] = 'categorical'
                profile['role'] = 'dimension'
                profile['semantic_tag'] = 'status'
                self.dimension_cols.append(col)
                self.categorical_cols.append(col)
                self.column_types[col] = 'categorical'
            elif card_ratio > 0.8 and n_unique_str > 20:
                if is_id_kw:
                    profile['dtype'] = 'text'
                    profile['role'] = 'key'
                    profile['semantic_tag'] = 'identifier'
                    self.key_cols.append(col)
                else:
                    avg_len = sample_vals.str.len().mean()
                    profile['dtype'] = 'text'
                    profile['role'] = 'text'
                    profile['semantic_tag'] = 'notes' if avg_len > 40 else 'text'
                    self.text_cols.append(col)
                self.column_types[col] = 'text'
            elif n_unique_str <= 60 and card_ratio <= 0.6:
                profile['dtype'] = 'categorical'
                profile['role'] = 'dimension'
                profile['semantic_tag'] = 'category'
                self.dimension_cols.append(col)
                self.categorical_cols.append(col)
                self.column_types[col] = 'categorical'
            else:
                profile['dtype'] = 'text'
                profile['role'] = 'text'
                profile['semantic_tag'] = 'text'
                self.text_cols.append(col)
                self.column_types[col] = 'text'

            self.column_profiles[col] = profile

        return self.column_profiles

    # Backward compat alias
    def detect_column_types(self):
        return self.profile_columns()

    # =========================================================
    # STEP 2 — DERIVED METRIC & ANOMALY DETECTION
    # =========================================================

    def detect_derived_metrics(self):
        """Step 2: Detect derived business metrics (Price × Quantity → Revenue, Dates → Duration)."""
        self.derived_metrics = []

        def _kw_match(col_name, keywords):
            col_lower = col_name.lower()
            return any(kw.lower() in col_lower for kw in keywords)

        # Price × Quantity → Revenue
        price_cols   = [c for c in self.measure_cols if _kw_match(c, self.PRICE_KEYWORDS)]
        qty_cols     = [c for c in self.measure_cols if _kw_match(c, self.QTY_KEYWORDS)]
        revenue_cols = [c for c in self.measure_cols if _kw_match(c, self.REVENUE_KEYWORDS)]

        if price_cols and qty_cols and not revenue_cols:
            p_col, q_col = price_cols[0], qty_cols[0]
            derived_values = self.df[p_col].fillna(0) * self.df[q_col].fillna(0)
            if derived_values.sum() > 0:
                self.derived_metrics.append({
                    'name':        f'الإيرادات ({p_col} × {q_col})',
                    'name_short':  'الإيرادات المحسوبة',
                    'formula':     f'{p_col} × {q_col}',
                    'type':        'revenue',
                    'col_a':       p_col,
                    'col_b':       q_col,
                    'values':      derived_values,
                    'icon':        'coins',
                    'label_suffix': '[محسوب]',
                })

        # Start date → End date → Duration
        start_cols = [c for c in self.datetime_cols if _kw_match(c, self.START_KW)]
        end_cols   = [c for c in self.datetime_cols if _kw_match(c, self.END_KW)]

        if start_cols and end_cols:
            s_col, e_col = start_cols[0], end_cols[0]
            try:
                duration = (self.df[e_col] - self.df[s_col]).dt.days
                if duration.dropna().median() > 0:
                    self.derived_metrics.append({
                        'name':        f'المدة (أيام) [{s_col} → {e_col}]',
                        'name_short':  'متوسط المدة (أيام)',
                        'formula':     f'{e_col} − {s_col}',
                        'type':        'duration',
                        'col_a':       s_col,
                        'col_b':       e_col,
                        'values':      duration,
                        'icon':        'clock',
                        'label_suffix': '[محسوب]',
                    })
            except Exception:
                pass

        # Detect Outliers / Anomalies for surface cards
        self._detect_anomalies()
        return self.derived_metrics

    def _detect_anomalies(self):
        """Detect extreme outliers in measure columns for explicit callout cards."""
        self.anomalies = []
        for col in self.measure_cols:
            series = self.df[col].dropna()
            if len(series) < 10:
                continue
            mean, std = series.mean(), series.std()
            if std == 0:
                continue
            z_scores = (series - mean) / std
            extreme = series[abs(z_scores) > 3.0]
            if len(extreme) > 0:
                max_out = extreme.abs().max()
                orig_val = series.loc[extreme.abs().idxmax()]
                self.anomalies.append({
                    'column': col,
                    'count': len(extreme),
                    'max_value': float(orig_val),
                    'mean': float(mean),
                    'z_score': round(float(abs(z_scores.loc[extreme.abs().idxmax()])), 1),
                })

    # =========================================================
    # STEP 3 & 4 — ADAPTIVE KPI GENERATION & VALIDATION
    # =========================================================

    def generate_kpis(self):
        """
        Step 3: Generate flexible 2–8 KPIs dynamically based on dataset character.
        - Small datasets (N < 35): 2-4 primary KPIs.
        - Categorical-heavy datasets: counts & status distributions.
        - Measure-rich datasets: derived metrics, totals, averages, best/worst.
        """
        kpis = []
        n_rows = len(self.df)
        is_small = n_rows < 35
        is_cat_heavy = len(self.dimension_cols) > len(self.measure_cols) or len(self.measure_cols) == 0

        # ── Priority 1: Derived metrics ──
        for dm in self.derived_metrics:
            vals = dm['values'].dropna()
            if len(vals) == 0:
                continue
            total = float(vals.sum())
            if total == 0:
                continue
            avg = float(vals.mean())
            trend, trend_value = self._calc_trend(dm['values'])

            kpis.append(self._validate_kpi({
                'label':    f"إجمالي {dm['name_short']} {dm['label_suffix']}",
                'value':    self._format_number(total),
                'raw_value': total,
                'kpi_type': 'derived',
                'icon':     dm.get('icon', 'calculator'),
                'color':    'success',
                'trend':    trend,
                'trend_value': trend_value,
            }))

            if not is_small:
                kpis.append(self._validate_kpi({
                    'label':    f"متوسط {dm['name_short']} {dm['label_suffix']}",
                    'value':    self._format_number(avg),
                    'raw_value': avg,
                    'kpi_type': 'derived_avg',
                    'icon':     'chart-bar',
                    'color':    'info',
                    'trend':    trend,
                    'trend_value': trend_value,
                }))

        # ── Priority 2: Categorical / Status summary KPI if cat-heavy ──
        if is_cat_heavy and self.dimension_cols:
            dim_col = self._best_dimension_col()
            if dim_col:
                top_vc = self.df[dim_col].value_counts()
                if len(top_vc) > 0:
                    top_cat = str(top_vc.index[0])
                    top_cnt = int(top_vc.iloc[0])
                    top_pct = round(top_cnt / n_rows * 100, 1)
                    kpis.append(self._validate_kpi({
                        'label':    f'التصنيف الأكثر تكراراً ({dim_col})',
                        'value':    top_cat,
                        'raw_value': top_cnt,
                        'subtitle': f'{top_cnt} سجل ({top_pct}%)',
                        'kpi_type': 'mode',
                        'icon':     'bullseye',
                        'color':    'primary',
                    }))

        # ── Priority 3: Measure columns ──
        priority_kw = [
            'مبيعات', 'إيرادات', 'ربح', 'تكلفة', 'سعر', 'كمية', 'عدد', 'مبلغ', 'قيمة', 'إجمالي',
            'sales', 'revenue', 'profit', 'cost', 'price', 'quantity', 'amount', 'total', 'score'
        ]

        scored = []
        for col in self.measure_cols:
            profile = self.column_profiles.get(col, {})
            if profile.get('role') != 'measure':
                continue
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            score = sum(10 for kw in priority_kw if kw in col.lower())
            if series.std() > 0 and series.mean() != 0:
                score += min(series.std() / abs(series.mean()) * 5, 10)
            scored.append((col, score, series))

        scored.sort(key=lambda x: x[1], reverse=True)
        max_measures = 2 if is_small else 3

        for col, _, series in scored[:max_measures]:
            total = float(series.sum())
            avg = float(series.mean())
            if total == 0 and avg == 0:
                continue
            trend, trend_value = self._calc_trend(self.df[col])

            kpis.append(self._validate_kpi({
                'label':    f'إجمالي {col}',
                'value':    self._format_number(total),
                'raw_value': total,
                'kpi_type': 'total',
                'icon':     'calculator',
                'color':    'primary',
                'trend':    trend,
                'trend_value': trend_value,
                'column':   col,
            }))

            if not is_small:
                kpis.append(self._validate_kpi({
                    'label':    f'متوسط {col}',
                    'value':    self._format_number(avg),
                    'raw_value': avg,
                    'kpi_type': 'average',
                    'icon':     'chart-bar',
                    'color':    'info',
                    'trend':    trend,
                    'trend_value': trend_value,
                    'column':   col,
                }))

        # ── Priority 4: Best / Worst dimension × measure ──
        if not is_small and self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()
            if self.derived_metrics:
                rank_series = self.derived_metrics[0]['values']
                rank_label = self.derived_metrics[0]['name_short']
            elif scored:
                rank_series = self.df[scored[0][0]]
                rank_label = scored[0][0]
            else:
                rank_series, rank_label = None, None

            if dim_col and rank_series is not None:
                try:
                    temp = self.df[[dim_col]].copy()
                    temp['__v__'] = rank_series.values
                    grouped = temp.dropna().groupby(dim_col)['__v__'].sum().sort_values(ascending=False)
                    if len(grouped) >= 2:
                        kpis.append(self._validate_kpi({
                            'label':    f'أعلى {dim_col} (بإجمالي {rank_label})',
                            'value':    str(grouped.index[0]),
                            'raw_value': float(grouped.iloc[0]),
                            'subtitle': self._format_number(float(grouped.iloc[0])),
                            'kpi_type': 'best',
                            'icon':     'trophy',
                            'color':    'success',
                            'trend':    'up',
                        }))
                except Exception:
                    pass

        # ── Priority 5: Record count ──
        kpis.append(self._validate_kpi({
            'label':    'إجمالي السجلات',
            'value':    f"{n_rows:,}",
            'raw_value': n_rows,
            'kpi_type': 'count',
            'icon':     'database',
            'color':    'secondary',
        }))

        # Filter out None and cap flexibly (2–8 KPIs)
        valid_kpis = [k for k in kpis if k is not None]
        max_kpis = 4 if is_small else 8
        return valid_kpis[:max_kpis]

    def _validate_kpi(self, kpi):
        """Step 5: Pre-render guard for KPI validity."""
        if not kpi:
            return None
        col = kpi.get('column')
        if col:
            profile = self.column_profiles.get(col, {})
            role = profile.get('role', 'measure')
            if role == 'key':
                return None
            if role == 'dimension' and kpi.get('kpi_type') in ('total', 'average'):
                count_val = self.df[col].nunique()
                kpi['label']     = f'عدد قيم {col} [تصحيح تلقائي]'
                kpi['value']     = str(count_val)
                kpi['raw_value'] = count_val
                kpi['icon']      = 'list'
                kpi['kpi_type']  = 'count'

        raw = kpi.get('raw_value')
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            return None

        return {
            'label':       kpi.get('label', ''),
            'value':       kpi.get('value', '—'),
            'raw_value':   raw,
            'subtitle':    kpi.get('subtitle', ''),
            'type':        kpi.get('kpi_type', ''),
            'icon':        kpi.get('icon', 'chart-bar'),
            'trend':       kpi.get('trend'),
            'trend_value': kpi.get('trend_value', 0),
            'color':       kpi.get('color', 'primary'),
        }

    def _calc_trend(self, series):
        """Calculate trend direction and percentage change if datetime column exists."""
        trend, trend_value = None, 0
        if not self.datetime_cols:
            return trend, trend_value
        try:
            dt_col = self.datetime_cols[0]
            temp = pd.DataFrame({'dt': self.df[dt_col], 'val': series.values}).dropna().sort_values('dt')
            if len(temp) >= 4:
                mid = len(temp) // 2
                first_h = temp['val'].iloc[:mid].mean()
                second_h = temp['val'].iloc[mid:].mean()
                if first_h != 0:
                    trend_value = round((second_h - first_h) / abs(first_h) * 100, 1)
                    trend = 'up' if trend_value > 0 else 'down' if trend_value < 0 else 'neutral'
        except Exception:
            pass
        return trend, trend_value

    # =========================================================
    # STEP 4 — DATA QUALITY & UNCERTAINTY REPORTING
    # =========================================================

    def assess_data_quality(self):
        """Step 4: Surface data quality, uncertainties, and low-confidence flags."""
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
                'message': f'يوجد {total_missing} قيمة مفقودة ({missing_pct}% من إجمالي الخلايا)',
                'icon': 'exclamation-triangle',
                'affected_column': None,
            })
            details['missing_by_column'] = {
                col: {'count': int(cnt), 'percentage': round(cnt / len(self.df) * 100, 1)}
                for col, cnt in missing_cols.items()
            }
            for col, cnt in missing_cols.items():
                pct = round(cnt / len(self.df) * 100, 1)
                if pct >= 20:
                    issues.append({
                        'type': 'missing_column',
                        'severity': 'warning',
                        'message': f'عمود "{col}": {pct}% قيم مفقودة — تم تطبيق الاستبعاد التلقائي',
                        'icon': 'minus-circle',
                        'affected_column': col,
                    })

        # Duplicates
        dup_count = int(self.df.duplicated().sum())
        if dup_count > 0:
            dup_pct = round(dup_count / len(self.df) * 100, 1)
            issues.append({
                'type': 'duplicates',
                'severity': 'warning',
                'message': f'يوجد {dup_count} صف مكرر ({dup_pct}% من الصفوف)',
                'icon': 'copy',
                'affected_column': None,
            })

        # Constant columns
        for col, profile in self.column_profiles.items():
            if profile.get('all_same') and profile.get('role') != 'key':
                issues.append({
                    'type': 'constant_column',
                    'severity': 'info',
                    'message': f'عمود "{col}" يحتوي على قيمة واحدة فقط — تم استبعاده من الرسومات',
                    'icon': 'ban',
                    'affected_column': col,
                })

        # Uncertainty & Ambiguity Flags (Step 4)
        for col, profile in self.column_profiles.items():
            note = profile.get('uncertainty_note')
            if note:
                issues.append({
                    'type': 'ambiguous_type',
                    'severity': 'info',
                    'message': note,
                    'icon': 'question-circle',
                    'affected_column': col,
                })

        # Anomalies
        if self.anomalies:
            for anom in self.anomalies:
                issues.append({
                    'type': 'outlier_anomalies',
                    'severity': 'warning',
                    'message': f'قيم شاذة في "{anom["column"]}": تم اكتشاف {anom["count"]} سجل متطرف (أعلى قيمة: {self._format_number(anom["max_value"])})',
                    'icon': 'chart-line',
                    'affected_column': anom['column'],
                })

        completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100.0

        if not issues:
            issues.append({
                'type': 'clean',
                'severity': 'success',
                'message': 'جودة البيانات ممتازة — لم يتم اكتشاف مشاكل أو فجوات',
                'icon': 'check-circle',
                'affected_column': None,
            })

        return {
            'issues': issues,
            'details': details,
            'completeness_score': completeness,
            'total_rows': len(self.df),
            'total_columns': len(self.df.columns),
            'measure_count': len(self.measure_cols),
            'dimension_count': len(self.dimension_cols),
            'key_count': len(self.key_cols),
        }

    # =========================================================
    # STEP 2 — CONTENT-DRIVEN ADAPTIVE CHARTS
    # =========================================================

    def recommend_charts(self):
        """
        Step 2: Generate charts adapted to data content & scale.
        - Donut/Pie: ONLY if categories <= 6 (else fallback to ranked bar).
        - Line chart: ONLY if datetime exists with >3 distinct points & signal.
        - Scatter plot: ONLY if correlation is non-trivial (|r| >= 0.35).
        - Small datasets (N < 35): simplified chart selection.
        """
        charts = []
        used = set()
        n_rows = len(self.df)
        is_small = n_rows < 35

        # ── 1. Datetime × Measure → Line Chart (ONLY if real temporal signal) ──
        if self.datetime_cols and (self.measure_cols or self.derived_metrics):
            dt_col = self.datetime_cols[0]
            dt_series = self.df[dt_col].dropna()
            if dt_series.nunique() >= 3:
                measure_items = [(dm['name_short'], dm['values'], dm['label_suffix']) for dm in self.derived_metrics]
                for mc in self.measure_cols[:2]:
                    measure_items.append((mc, self.df[mc], ''))

                for m_name, m_series, m_suffix in measure_items[:2]:
                    combo = f'line_{dt_col}_{m_name}'
                    if combo in used:
                        continue
                    used.add(combo)
                    try:
                        temp = pd.DataFrame({'dt': self.df[dt_col], 'val': m_series.values}).dropna().sort_values('dt')
                        if len(temp) < 3:
                            continue
                        if len(temp) > 100:
                            temp = temp.set_index('dt').resample('W').mean().reset_index()
                        elif len(temp) > 50:
                            temp = temp.set_index('dt').resample('D').mean().reset_index().dropna()

                        labels = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in temp['dt']]
                        values = [round(float(x), 2) if pd.notna(x) else None for x in temp['val']]

                        # Check if line chart actually has signal (variance > 0)
                        clean_vals = [v for v in values if v is not None]
                        if len(clean_vals) >= 3 and np.std(clean_vals) > 0:
                            charts.append({
                                'id': f'chart_{len(charts)}',
                                'type': 'line',
                                'title': f'الاتجاه الزمني لمقياس {m_name} {m_suffix}'.strip(),
                                'data': {
                                    'labels': labels,
                                    'datasets': [{
                                        'label': f'{m_name} {m_suffix}'.strip(),
                                        'data': values,
                                        'borderColor': '#4f46e5',
                                        'backgroundColor': 'rgba(79, 70, 229, 0.1)',
                                        'fill': True,
                                        'tension': 0.4,
                                    }]
                                },
                                'priority': 12
                            })
                    except Exception:
                        pass

        # ── 2. Dimension × Measure → Bar Chart OR Ranked Bar ──
        if self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()
            if dim_col:
                if self.derived_metrics:
                    dm = self.derived_metrics[0]
                    measure_name = dm['name_short']
                    suffix = dm['label_suffix']
                    temp = self.df[[dim_col]].copy()
                    temp['__v__'] = dm['values'].values
                    grouped = temp.dropna().groupby(dim_col)['__v__'].sum().sort_values(ascending=False).head(15)
                else:
                    m_col = self._best_measure_col()
                    measure_name = m_col
                    suffix = ''
                    grouped = self.df.groupby(dim_col)[m_col].sum().sort_values(ascending=False).head(15) if m_col else None

                combo = f'bar_{dim_col}_{measure_name}'
                if combo not in used and grouped is not None and len(grouped) >= 2:
                    used.add(combo)
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'bar',
                        'title': f'توزيع إجمالي {measure_name} حسب {dim_col} {suffix}'.strip(),
                        'data': {
                            'labels': [str(x) for x in grouped.index.tolist()],
                            'datasets': [{
                                'label': f'إجمالي {measure_name}',
                                'data': [round(float(x), 2) for x in grouped.values.tolist()],
                                'backgroundColor': self._get_color_palette(len(grouped)),
                                'borderRadius': 6,
                            }]
                        },
                        'priority': 10
                    })

        # ── 3. Part-to-Whole Doughnut (ONLY if categories <= 6) ──
        if self.dimension_cols:
            dim_col = self._best_dimension_col()
            if dim_col:
                vc = self.df[dim_col].value_counts()
                n_cats = len(vc)
                if 2 <= n_cats <= 6:
                    # Doughnut chart is readable for <= 6 slices
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'doughnut',
                        'title': f'النسبة المئوية لتوزيع {dim_col}',
                        'data': {
                            'labels': [str(x) for x in vc.index.tolist()],
                            'datasets': [{
                                'data': [int(x) for x in vc.values.tolist()],
                                'backgroundColor': self._get_color_palette(len(vc)),
                                'borderWidth': 2,
                                'borderColor': '#ffffff',
                            }]
                        },
                        'priority': 8
                    })
                elif n_cats > 6:
                    # Fallback to ranked bar for > 6 categories (readable)
                    vc_head = vc.head(10)
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'bar',
                        'title': f'أعلى 10 فئات تكراراً في {dim_col}',
                        'data': {
                            'labels': [str(x) for x in vc_head.index.tolist()],
                            'datasets': [{
                                'label': 'عدد السجلات',
                                'data': [int(x) for x in vc_head.values.tolist()],
                                'backgroundColor': self._get_color_palette(len(vc_head)),
                                'borderRadius': 4,
                            }]
                        },
                        'priority': 7
                    })

        # ── 4. Two measures → Scatter Plot (ONLY if real correlation |r| >= 0.35) ──
        if not is_small and len(self.measure_cols) >= 2:
            col1, col2 = self.measure_cols[0], self.measure_cols[1]
            combo = f'scatter_{col1}_{col2}'
            if combo not in used:
                used.add(combo)
                temp = self.df[[col1, col2]].dropna()
                if len(temp) > 10:
                    corr = temp[col1].corr(temp[col2])
                    if pd.notna(corr) and abs(corr) >= 0.35:  # Only plot if non-trivial correlation exists!
                        corr_desc = f' (ارتباط {"طردي" if corr > 0 else "عكسي"} {round(abs(corr), 2)})'
                        if len(temp) > 500:
                            temp = temp.sample(500, random_state=42)
                        charts.append({
                            'id': f'chart_{len(charts)}',
                            'type': 'scatter',
                            'title': f'علاقة {col1} مع {col2}{corr_desc}',
                            'data': {
                                'datasets': [{
                                    'label': f'{col1} مقابل {col2}',
                                    'data': [{'x': round(float(r[col1]), 2), 'y': round(float(r[col2]), 2)} for _, r in temp.iterrows()],
                                    'backgroundColor': 'rgba(79, 70, 229, 0.5)',
                                    'pointRadius': 4,
                                }]
                            },
                            'correlation': round(float(corr), 3),
                            'priority': 6
                        })

        # ── 5. Measure Histogram (if numeric & sample >= 20) ──
        best_m = self._best_measure_col()
        if not is_small and best_m:
            series = self.df[best_m].dropna()
            if len(series) >= 20:
                hist_vals, bin_edges = np.histogram(series, bins=min(15, max(5, len(series) // 10)))
                bin_labels = [f"{round(float(bin_edges[i]), 1)}–{round(float(bin_edges[i+1]), 1)}" for i in range(len(hist_vals))]
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'bar',
                    'title': f'توزيع القيم لـ {best_m} (هستوغرام)',
                    'data': {
                        'labels': bin_labels,
                        'datasets': [{
                            'label': 'التكرار',
                            'data': [int(x) for x in hist_vals.tolist()],
                            'backgroundColor': 'rgba(16, 185, 129, 0.7)',
                            'borderColor': '#10b981',
                            'borderWidth': 1,
                            'borderRadius': 4,
                        }]
                    },
                    'priority': 5
                })

        charts.sort(key=lambda x: x.get('priority', 0), reverse=True)
        max_charts = 3 if is_small else 6
        return charts[:max_charts]

    # =========================================================
    # STEP 5 — EMPIRICAL ARABIC NARRATIVE & INSIGHTS
    # =========================================================

    def detect_trends(self):
        """Detect significant trends, concentrations, and correlations."""
        trends = []

        # Time series trends
        if self.datetime_cols and (self.measure_cols or self.derived_metrics):
            dt_col = self.datetime_cols[0]
            measure_items = [(dm['name_short'], dm['values']) for dm in self.derived_metrics]
            for mc in self.measure_cols[:3]:
                measure_items.append((mc, self.df[mc]))

            for m_name, m_series in measure_items[:3]:
                try:
                    m_vals = m_series.values if hasattr(m_series, 'values') else m_series
                    temp = pd.DataFrame({'dt': self.df[dt_col], 'val': m_vals}).dropna().sort_values('dt')
                    if len(temp) < 5:
                        continue

                    x = np.arange(len(temp))
                    y = temp['val'].values.astype(float)
                    slope, _, r_val, p_val, _ = stats.linregress(x, y)

                    if p_val < 0.05:
                        first_val = y[0] if y[0] != 0 else 1
                        pct = round((y[-1] - y[0]) / abs(first_val) * 100, 1)
                        direction = 'ارتفاع' if slope > 0 else 'انخفاض'
                        trends.append({
                            'type': 'trend',
                            'column': m_name,
                            'direction': 'up' if slope > 0 else 'down',
                            'message': f'{direction} في {m_name} بنسبة {abs(pct)}% عبر الترتيب الزمني',
                            'r_squared': round(float(r_val ** 2), 3),
                            'significance': 'high' if p_val < 0.01 else 'medium'
                        })
                except Exception:
                    continue

        # Concentration (top 3 share)
        if self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()
            if self.derived_metrics:
                m_series, m_name = self.derived_metrics[0]['values'], self.derived_metrics[0]['name_short']
            else:
                m_col = self._best_measure_col()
                m_series, m_name = (self.df[m_col], m_col) if m_col else (None, None)

            if dim_col and m_series is not None:
                try:
                    temp = self.df[[dim_col]].copy()
                    temp['__v__'] = m_series.values
                    grouped = temp.dropna().groupby(dim_col)['__v__'].sum().sort_values(ascending=False)
                    if len(grouped) >= 3:
                        top3 = grouped.head(3)
                        total = grouped.sum()
                        if total > 0:
                            top_pct = round(top3.sum() / total * 100, 1)
                            top_names = '، '.join([f'"{x}"' for x in top3.index[:3]])
                            trends.append({
                                'type': 'concentration',
                                'column': dim_col,
                                'direction': 'neutral',
                                'message': f'أعلى 3 فئات في {dim_col} ({top_names}) تستحوذ على {top_pct}% من إجمالي {m_name}',
                                'significance': 'high' if top_pct > 60 else 'medium'
                            })
                except Exception:
                    pass

        # Correlation
        if len(self.measure_cols) >= 2:
            col1, col2 = self.measure_cols[0], self.measure_cols[1]
            try:
                corr = self.df[col1].corr(self.df[col2])
                if pd.notna(corr) and abs(corr) > 0.4:
                    direction = 'طردي' if corr > 0 else 'عكسي'
                    trends.append({
                        'type': 'correlation',
                        'column': f'{col1} & {col2}',
                        'direction': 'up' if corr > 0 else 'down',
                        'message': f'ارتباط {direction} ملحوظ ({round(abs(corr), 2)}) بين {col1} و {col2}',
                        'significance': 'high' if abs(corr) > 0.75 else 'medium'
                    })
            except Exception:
                pass

        return trends

    def generate_narrative(self, kpis, trends, quality):
        """Step 5: Generate dynamic Arabic executive summary referencing exact empirical findings."""
        sentences = []
        rows, cols = len(self.df), len(self.df.columns)

        if rows < 35:
            sentences.append(f'يحتوي مجموع البيانات على {rows} سجل فقط عبر {cols} عمود (حجم عينة صغير نسبياً).')
        else:
            sentences.append(f'يحتوي الملف على {rows:,} سجل موزعة عبر {cols} عمود.')

        if self.derived_metrics:
            dm = self.derived_metrics[0]
            total = self._format_number(float(dm['values'].sum()))
            sentences.append(f'تم احتساب مقياس {dm["name_short"]} تلقائياً بقيمة إجمالية تبلغ {total}.')

        high_trends = [t for t in trends if t.get('significance') == 'high']
        if high_trends:
            sentences.append(high_trends[0]['message'] + '.')

        concentration = [t for t in trends if t['type'] == 'concentration']
        if concentration:
            sentences.append(concentration[0]['message'] + '.')

        if self.anomalies:
            anom = self.anomalies[0]
            sentences.append(f'ملاحظة: تم اكتشاف قيم متطرفة في {anom["column"]} تصل إلى {self._format_number(anom["max_value"])}.')

        if quality['completeness_score'] < 90:
            sentences.append(f'تنبيه: اكتمال البيانات {quality["completeness_score"]}% — يرجى مراجعة الفجوات.')

        return ' '.join(sentences[:4])

    def generate_insights(self, trends, quality):
        """Step 5: Actionable insights lead by the headline business findings."""
        insights = []

        if self.anomalies:
            anom = self.anomalies[0]
            insights.append({
                'category': 'انحراف متطرف',
                'icon': 'exclamation-circle',
                'color': 'danger',
                'title': f'قيم متطرفة في {anom["column"]}',
                'description': f'تم اكتشاف {anom["count"]} سجل يحيد بشدة عن المتوسط. أعلى قيمة هي {self._format_number(anom["max_value"])}.',
                'priority': 'high'
            })

        for trend in trends:
            if trend['type'] == 'trend' and trend['direction'] == 'up':
                insights.append({
                    'category': 'اتجاه صاعد',
                    'icon': 'arrow-up',
                    'color': 'success',
                    'title': f'نمو في {trend["column"]}',
                    'description': trend['message'] + '. يستحسن تعزيز العوامل المساهمة.',
                    'priority': 'high'
                })
            elif trend['type'] == 'concentration':
                insights.append({
                    'category': 'تركز في الفئات',
                    'icon': 'chart-pie',
                    'color': 'info',
                    'title': f'تركز عالي في {trend["column"]}',
                    'description': trend['message'] + '. يشير إلى اعتماد كبير على عناصر محدودة.',
                    'priority': 'medium'
                })
            elif trend['type'] == 'correlation':
                insights.append({
                    'category': 'علاقة بين متغيرة',
                    'icon': 'link',
                    'color': 'primary',
                    'title': f'ارتباط بين {trend["column"]}',
                    'description': trend['message'] + '. يمكن استغلال هذه العلاقة في التخطيط.',
                    'priority': 'medium'
                })

        if self.derived_metrics:
            for dm in self.derived_metrics:
                insights.append({
                    'category': 'مقياس محسوب',
                    'icon': 'calculator',
                    'color': 'primary',
                    'title': f'احتساب {dm["name_short"]}',
                    'description': f'الصيغة: {dm["formula"]}. يعكس النتائج الفعلية بدقة بدلاً من الأعمدة المفردة.',
                    'priority': 'medium'
                })

        if not insights:
            insights.append({
                'category': 'ملاحظة عامة',
                'icon': 'check-circle',
                'color': 'success',
                'title': 'بيانات متوازنة',
                'description': 'البيانات تبدو متسقة ومستقرة دون انحرافات حادة.',
                'priority': 'low'
            })

        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 3))
        return insights

    # =========================================================
    # PIPELINE RUNNERS
    # =========================================================

    # =========================================================
    # PIPELINE RUNNERS (AI-DRIVEN WITH SAFE FALLBACK)
    # =========================================================

    def run_full_analysis(self):
        """Run complete analysis with Claude API reasoning and safe fallback."""
        try:
            self.load_data()
            self.profile_columns()
            self.detect_derived_metrics()

            # Attempt AI pipeline
            ai_result = self._run_ai_pipeline(custom_query="")
            if ai_result:
                ai_result['analysis_mode'] = 'auto'
                return ai_result

            # Fallback to local analysis if AI unavailable
            return self._run_fallback_analysis(analysis_mode='auto', custom_query="")
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'خطأ غير متوقع: {str(e)}', 'trace': traceback.format_exc()}

    def run_custom_analysis(self, query_text):
        """Run custom analysis with Claude API reasoning and safe fallback."""
        try:
            self.load_data()
            self.profile_columns()
            self.detect_derived_metrics()

            if not query_text or not query_text.strip():
                return {'success': False, 'error': 'يرجى إدخال نص الطلب المخصص'}

            # Attempt AI pipeline with custom query
            ai_result = self._run_ai_pipeline(custom_query=query_text)
            if ai_result:
                ai_result['analysis_mode'] = 'custom'
                ai_result['custom_query'] = query_text
                return ai_result

            # Fallback to local custom analysis
            return self._run_fallback_analysis(analysis_mode='custom', custom_query=query_text)
        except Exception as e:
            return {'success': False, 'error': f'خطأ في معالجة التحليل المخصص: {str(e)}'}

    def _run_ai_pipeline(self, custom_query=""):
        """Execute AI reasoning pipeline via AIService and compute pandas metrics."""
        ai_res = AIService.analyze_dataset(self.df, custom_query=custom_query)
        if not ai_res:
            return None

        # 1. Apply column roles from AI
        col_roles = ai_res.get('column_roles', {})
        for col, role in col_roles.items():
            if col in self.df.columns:
                if role == 'identifier':
                    if col not in self.key_cols:
                        self.key_cols.append(col)
                    if col in self.measure_cols:
                        self.measure_cols.remove(col)
                elif role == 'measure':
                    if col not in self.measure_cols and col not in self.key_cols:
                        self.measure_cols.append(col)
                elif role == 'dimension':
                    if col not in self.dimension_cols:
                        self.dimension_cols.append(col)
                elif role == 'date':
                    if col not in self.datetime_cols:
                        self.datetime_cols.append(col)

        # 2. Compute dynamic KPIs based on recommended_kpis
        computed_kpis = []
        for kpi_spec in ai_res.get('recommended_kpis', []):
            kpi_obj = self._compute_ai_kpi(kpi_spec)
            if kpi_obj:
                computed_kpis.append(kpi_obj)

        if len(computed_kpis) < 2:
            computed_kpis.extend([k for k in self.generate_kpis() if k is not None])
            computed_kpis = computed_kpis[:6]

        # 3. Compute dynamic Charts based on recommended_charts
        computed_charts = []
        for chart_spec in ai_res.get('recommended_charts', []):
            chart_obj = self._compute_ai_chart(chart_spec)
            if chart_obj:
                computed_charts.append(chart_obj)

        if not computed_charts:
            computed_charts = self.recommend_charts()

        # 4. Process data quality flags
        empirical_quality = self.assess_data_quality()
        ai_flags = ai_res.get('data_quality_flags', [])
        issues = empirical_quality.get('issues', [])
        for flag in ai_flags:
            issues.append({
                'type': 'ai_flag',
                'severity': flag.get('severity', 'medium'),
                'icon': 'exclamation-triangle',
                'message': f"{flag.get('issue')} (الأعمدة: {', '.join(flag.get('columns', []))})" if flag.get('columns') else flag.get('issue')
            })
        empirical_quality['issues'] = issues

        # 5. Checklist verification & server-side audit
        checklist = ai_res.get('requested_items_checklist', [])
        fulfilled_count = sum(1 for item in checklist if item.get('fulfilled'))
        total_requested = len(checklist)

        rendered_count = len(computed_kpis) + len(computed_charts)
        if total_requested > 0 and fulfilled_count > rendered_count:
            logger.warning(f"Checklist count ({fulfilled_count}) exceeds rendered widgets ({rendered_count}). Adding server note.")
            empirical_quality['issues'].append({
                'type': 'audit_note',
                'severity': 'warning',
                'icon': 'info-circle',
                'message': f"تم التحقق من الطلب: {fulfilled_count} من {total_requested} متطلبات منفذة، وتم توثيق الباقي."
            })

        # 6. Executive Narrative Summary in Arabic
        insights = ai_res.get('key_insights', [])
        narrative = " ".join(insights) if insights else self.generate_narrative(computed_kpis, self.detect_trends(), empirical_quality)

        formatted_insights = []
        for idx, ins in enumerate(insights):
            formatted_insights.append({
                'title': f'ملاحظة تحليليية #{idx+1}',
                'category': 'رؤية الذكاء الاصطناعي',
                'description': ins,
                'color': 'primary',
                'icon': 'lightbulb'
            })

        return {
            'success': True,
            'is_ai_analysis': True,
            'is_ai_fallback': False,
            'sheet_name': self.sheet_name,
            'row_count': len(self.df),
            'col_count': len(self.df.columns),
            'column_types': self.column_types,
            'columns': list(self.df.columns),
            'narrative': narrative,
            'quality': empirical_quality,
            'kpis': computed_kpis,
            'charts': computed_charts,
            'trends': self.detect_trends(),
            'insights': formatted_insights,
            'filters': self._get_filter_options(),
            'requested_items_checklist': checklist,
            'ai_metadata': {
                'column_roles': col_roles,
                'derived_metrics': ai_res.get('derived_metrics', [])
            }
        }

    def _compute_ai_kpi(self, spec):
        """Compute KPI metric values safely in pandas following AI specification."""
        try:
            label = spec.get('label', 'مؤشر أداء')
            target_col = spec.get('target_column') or (spec.get('columns_used')[0] if spec.get('columns_used') else None)
            op = (spec.get('operation') or 'sum').lower()
            val_desc = spec.get('value_description', '')

            if not target_col or target_col not in self.df.columns:
                target_col = self._best_measure_col()

            # Rule 1: ID columns MUST NEVER be aggregated with sum/mean/min/max
            if target_col in self.key_cols or target_col in self.text_cols:
                op = 'count'

            series = self.df[target_col].dropna() if target_col else pd.Series()
            if len(series) == 0:
                return None

            if op == 'count':
                formatted_val = f"{len(series):,}"
                sub = val_desc or f"عدد السجلات الحالية لحقل {target_col}"
            elif op == 'mean':
                mean_val = float(series.mean())
                formatted_val = self._format_number(mean_val)
                sub = val_desc or f"المتوسط الحسابي بناءً على {target_col}"
            elif op == 'max':
                max_val = float(series.max())
                top_row = self.df.loc[series.idxmax()] if len(series) > 0 else None
                dim_info = ""
                if top_row is not None and self.dimension_cols:
                    best_dim = self._best_dimension_col()
                    if best_dim and best_dim in top_row:
                        dim_info = f" ({top_row[best_dim]})"
                formatted_val = f"{self._format_number(max_val)}{dim_info}"
                sub = val_desc or f"أعلى قيمة بناءً على {target_col}"
            elif op == 'min':
                min_val = float(series.min())
                bot_row = self.df.loc[series.idxmin()] if len(series) > 0 else None
                dim_info = ""
                if bot_row is not None and self.dimension_cols:
                    best_dim = self._best_dimension_col()
                    if best_dim and best_dim in bot_row:
                        dim_info = f" ({bot_row[best_dim]})"
                formatted_val = f"{self._format_number(min_val)}{dim_info}"
                sub = val_desc or f"أدنى قيمة بناءً على {target_col}"
            else:
                sum_val = float(series.sum())
                formatted_val = self._format_number(sum_val)
                sub = val_desc or f"الإجمالي الكلي بناءً على {target_col}"

            return {
                'label': label,
                'value': formatted_val,
                'subtitle': sub,
                'icon': 'chart-line' if op == 'mean' else ('chart-pie' if op == 'count' else 'coins'),
                'color': 'primary',
                'trend': 'neutral'
            }
        except Exception as e:
            logger.error(f"Error computing AI KPI ({spec}): {e}")
            return None

    def _compute_ai_chart(self, spec):
        """Construct Chart.js config dynamically based on pandas aggregation of spec."""
        try:
            chart_type = (spec.get('type') or 'bar').lower()
            title = spec.get('title', 'رسم بياني تحليلي')
            x_col = spec.get('x')
            y_col = spec.get('y')
            agg = (spec.get('aggregation') or 'sum').lower()

            if not x_col or x_col not in self.df.columns:
                x_col = self._best_dimension_col() or (self.datetime_cols[0] if self.datetime_cols else None)
            if not y_col or y_col not in self.df.columns:
                y_col = self._best_measure_col()

            if not x_col or not y_col:
                return None

            # Handle Scatter Plot
            if chart_type == 'scatter':
                valid_df = self.df[[x_col, y_col]].dropna()
                scatter_data = []
                for _, r in valid_df.head(200).iterrows():
                    try:
                        scatter_data.append({'x': float(r[x_col]), 'y': float(r[y_col])})
                    except Exception:
                        pass

                return {
                    'type': 'scatter',
                    'title': title,
                    'fullWidth': True,
                    'data': {
                        'datasets': [{
                            'label': f'الارتباط بين {x_col} و {y_col}',
                            'data': scatter_data,
                            'backgroundColor': '#4f46e5',
                            'borderColor': '#4f46e5'
                        }]
                    },
                    'options': {
                        'responsive': True,
                        'scales': {
                            'x': {'title': {'display': True, 'text': x_col}},
                            'y': {'title': {'display': True, 'text': y_col}}
                        }
                    }
                }

            # ID protection: If Y is an identifier, force 'count'
            if y_col in self.key_cols or y_col in self.text_cols:
                agg = 'count'

            df_clean = self.df[[x_col, y_col]].dropna()
            if df_clean.empty:
                return None

            if agg == 'mean':
                grouped = df_clean.groupby(x_col)[y_col].mean().head(15)
            elif agg == 'count':
                grouped = df_clean.groupby(x_col)[y_col].count().head(15)
            else:
                grouped = df_clean.groupby(x_col)[y_col].sum().head(15)

            labels = [str(k) for k in grouped.index]
            values = [round(float(v), 2) for v in grouped.values]

            palette = self._get_color_palette(len(labels))

            dataset_config = {
                'label': f"{y_col} ({'متوسط' if agg=='mean' else ('عدد' if agg=='count' else 'إجمالي')})",
                'data': values,
                'backgroundColor': palette if chart_type in ['pie', 'doughnut'] else palette[0],
                'borderColor': palette if chart_type in ['pie', 'doughnut'] else palette[0],
                'borderWidth': 1
            }

            return {
                'type': chart_type,
                'title': title,
                'fullWidth': chart_type in ['line', 'scatter'],
                'data': {
                    'labels': labels,
                    'datasets': [dataset_config]
                },
                'options': {
                    'responsive': True,
                    'plugins': {
                        'legend': {'display': chart_type in ['pie', 'doughnut']}
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error computing AI Chart ({spec}): {e}")
            return None

    def _run_fallback_analysis(self, analysis_mode='auto', custom_query=""):
        """Safely generate simplified local analysis when AI service is unavailable."""
        quality   = self.assess_data_quality()
        kpis      = self.generate_kpis()
        charts    = self.recommend_charts()
        trends    = self.detect_trends()
        narrative = self.generate_narrative(kpis, trends, quality)
        insights  = self.generate_insights(trends, quality)
        filters   = self._get_filter_options()

        return {
            'success': True,
            'is_ai_analysis': False,
            'is_ai_fallback': True,
            'fallback_reason': 'تحليل مبسط — خدمة الذكاء الاصطناعي غير متوفرة حالياً',
            'analysis_mode': analysis_mode,
            'custom_query': custom_query,
            'sheet_name': self.sheet_name,
            'row_count': len(self.df),
            'col_count': len(self.df.columns),
            'column_types': self.column_types,
            'columns': list(self.df.columns),
            'narrative': narrative,
            'quality':   quality,
            'kpis':      [k for k in kpis if k is not None],
            'charts':    charts,
            'trends':    trends,
            'insights':  insights,
            'filters':   filters,
        }


    def run_filtered_analysis(self, filters_dict):
        try:
            self.load_data()
            self.profile_columns()
            self.detect_derived_metrics()

            date_from = filters_dict.get('date_from')
            date_to   = filters_dict.get('date_to')
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

            category        = filters_dict.get('category')
            category_column = filters_dict.get('category_column')
            if category and category_column and category_column in self.dimension_cols:
                self.df = self.df[self.df[category_column].astype(str) == category]

            if self.df.empty:
                return {'success': False, 'error': 'لا توجد بيانات تطابق معايير التصفية المحددة'}

            self.measure_cols    = [c for c in self.measure_cols    if c in self.df.columns]
            self.dimension_cols  = [c for c in self.dimension_cols  if c in self.df.columns]
            self.datetime_cols   = [c for c in self.datetime_cols   if c in self.df.columns]
            self.numeric_cols    = self.measure_cols
            self.categorical_cols = self.dimension_cols

            quality   = self.assess_data_quality()
            kpis      = self.generate_kpis()
            charts    = self.recommend_charts()
            trends    = self.detect_trends()
            narrative = self.generate_narrative(kpis, trends, quality)
            insights  = self.generate_insights(trends, quality)

            return {
                'success': True,
                'kpis':      [k for k in kpis if k is not None],
                'charts':    charts,
                'narrative': narrative,
                'trends':    trends,
                'insights':  insights,
                'quality':   quality,
                'filtered_rows': len(self.df),
                'filters':   self._get_filter_options(),
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # =========================================================
    # HELPERS
    # =========================================================

    def _best_dimension_col(self):
        best, best_score = None, -1
        for col in self.dimension_cols:
            profile = self.column_profiles.get(col, {})
            n = self.df[col].nunique()
            score = 10 - abs(n - 8)
            if 3 <= n <= 20:
                score += 5
            if profile.get('dtype') == 'categorical':
                score += 8
            if profile.get('all_same'):
                score -= 20
            if score > best_score:
                best_score = score
                best = col
        return best or (self.dimension_cols[0] if self.dimension_cols else None)

    def _best_categorical_col(self):
        return self._best_dimension_col()

    def _best_measure_col(self):
        if not self.measure_cols:
            return None
        priority_kw = [
            'مبيعات', 'إيرادات', 'ربح', 'تكلفة', 'سعر', 'كمية',
            'sales', 'revenue', 'profit', 'cost', 'price', 'amount', 'total', 'score'
        ]
        best, best_score = None, -1
        for col in self.measure_cols:
            score = sum(10 for kw in priority_kw if kw in col.lower())
            series = self.df[col].dropna()
            if len(series) > 0 and series.std() > 0:
                score += 5
            if score > best_score:
                best_score = score
                best = col
        return best or self.measure_cols[0]

    def _best_numeric_col(self):
        return self._best_measure_col()

    def _format_number(self, num):
        if not isinstance(num, (int, float)) or (isinstance(num, float) and np.isnan(num)):
            return '—'
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
        palette = [
            '#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
            '#06b6d4', '#ec4899', '#14b8a6', '#f97316', '#6366f1',
            '#84cc16', '#e11d48', '#0891b2', '#a855f7', '#65a30d',
        ]
        return (palette * ((n // len(palette)) + 1))[:n]

    def _get_filter_options(self):
        filters = {}
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

        if self.dimension_cols:
            filters['categories'] = {}
            for col in self.dimension_cols[:3]:
                values = self.df[col].dropna().unique().tolist()
                filters['categories'][col] = [str(v) for v in values[:50]]

        return filters
