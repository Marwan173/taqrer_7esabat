"""
Core data analysis engine — Professional 5-Step Analysis Process.

Step 1: Profile every column (dtype, role, cardinality, missing values, confidence)
Step 2: Detect derived metrics (Price×Quantity→Revenue, StartDate→EndDate→Duration)
Step 3: Generate KPIs using only role-appropriate operations
Step 4: Surface data quality issues transparently (per-column, flagged, not silenced)
Step 5: Validate every KPI before rendering — skip or auto-correct mismatches
"""
import pandas as pd
import numpy as np
from scipy import stats
import traceback
import re


class DataAnalyzer:
    """Professional data analysis engine implementing the 5-step analysis process."""

    ARABIC_MONTHS = {
        1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل',
        5: 'مايو', 6: 'يونيو', 7: 'يوليو', 8: 'أغسطس',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }

    # Keyword sets for derived metric detection (Step 2)
    PRICE_KEYWORDS    = ['price', 'سعر', 'unit_price', 'سعر_وحدة', 'سعر الوحدة', 'تكلفة', 'cost', 'rate', 'معدل', 'سعر_البيع']
    QTY_KEYWORDS      = ['quantity', 'qty', 'كمية', 'عدد', 'units', 'وحدات', 'pieces', 'كميه', 'الكمية']
    REVENUE_KEYWORDS  = ['revenue', 'مبيعات', 'إيرادات', 'total', 'إجمالي', 'sales', 'amount', 'مبلغ', 'قيمة_المبيعات']
    START_KW          = ['start', 'begin', 'بداية', 'تاريخ_البداية', 'from', 'open', 'created', 'تاريخ_الفتح']
    END_KW            = ['end', 'close', 'نهاية', 'تاريخ_النهاية', 'to', 'finish', 'completed', 'closed', 'تاريخ_الاغلاق']

    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None
        self.original_df = None
        self.sheet_name = ''

        # Step 1: Full column profiles
        self.column_profiles = {}   # {col: {role, dtype, cardinality, missing, all_same, confidence, ...}}

        # Categorized column lists derived from profiles
        self.measure_cols    = []   # role='measure'  — numeric, sum/avg are meaningful
        self.dimension_cols  = []   # role='dimension' — categorical, meaningful to group by
        self.datetime_cols   = []   # role='datetime'
        self.key_cols        = []   # role='key'       — unique IDs, NEVER calculated
        self.text_cols       = []   # role='text'      — high-cardinality free text

        # Backward-compatibility aliases (used by some helper methods)
        self.numeric_cols    = []   # = measure_cols
        self.categorical_cols = []  # = dimension_cols
        self.column_types    = {}   # {col: 'numeric'|'categorical'|'datetime'|'text'} for API

        # Step 2: Derived metrics (computed, not stored)
        self.derived_metrics = []

    # =========================================================
    # DATA LOADING
    # =========================================================

    def load_data(self):
        """Load Excel file and select the best non-empty sheet."""
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
    # STEP 1 — COLUMN PROFILER
    # =========================================================

    def profile_columns(self):
        """
        Step 1: Profile every column to determine:
          - dtype (numeric / categorical / datetime / text)
          - role  (measure / dimension / datetime / key / text)
          - cardinality ratio
          - missing count & percentage
          - all_same flag (column is constant — useless)
          - confidence (high/medium/low based on inference quality)
          - mixed_format flag (inconsistent values within a column)
          - coerced flag (type was inferred, not native)

        Roles:
          measure   — numeric, meaningful to sum/average
          dimension — categorical, meaningful to group by
          datetime  — date/time column for trends
          key       — unique identifier, NEVER used in calculations
          text      — high-cardinality free text, limited analytical value
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
                'confidence': 'high',
                'coerced': False,
                'mixed_format': False,
            }

            if n_non_null == 0:
                profile['dtype'] = 'empty'
                profile['role'] = 'text'
                self.column_profiles[col] = profile
                self.text_cols.append(col)
                self.column_types[col] = 'text'
                continue

            # Flag: only one unique non-null value → constant column, useless for analysis
            if non_null.nunique() <= 1:
                profile['all_same'] = True

            # ── 1. Datetime ──
            if pd.api.types.is_datetime64_any_dtype(series):
                profile['dtype'] = 'datetime'
                profile['role'] = 'datetime'
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
                        profile['coerced'] = True
                        profile['confidence'] = 'high' if parse_rate > 0.95 else 'medium'
                        self.column_profiles[col] = profile
                        self.datetime_cols.append(col)
                        self.column_types[col] = 'datetime'
                        continue
                except Exception:
                    pass

            # ── 2. Numeric ──
            is_numeric = pd.api.types.is_numeric_dtype(series)
            coerce_rate = 0.0

            if not is_numeric and series.dtype == object:
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
                except Exception:
                    pass

            if is_numeric:
                num_series = self.df[col].dropna()
                n_unique_num = int(num_series.nunique())
                card_ratio = n_unique_num / len(num_series) if len(num_series) > 0 else 0

                profile['n_unique'] = n_unique_num
                profile['cardinality_ratio'] = round(card_ratio, 3)
                profile['dtype'] = 'numeric'

                col_lower = col.lower()
                id_keywords = ['id', 'رقم', 'code', 'كود', 'رمز', '#', 'num', 'seq', 'no', 'number', 'index']
                looks_like_id = (
                    card_ratio > 0.9
                    and n_unique_num > 30
                    and any(kw in col_lower for kw in id_keywords)
                )

                if looks_like_id:
                    profile['role'] = 'key'
                    self.key_cols.append(col)
                    self.column_types[col] = 'numeric'
                elif n_unique_num <= 15 and card_ratio < 0.05:
                    # Low cardinality numeric → dimension (e.g. rating 1–5, quarter 1–4)
                    profile['role'] = 'dimension'
                    self.dimension_cols.append(col)
                    self.categorical_cols.append(col)
                    self.column_types[col] = 'categorical'
                else:
                    profile['role'] = 'measure'
                    self.measure_cols.append(col)
                    self.numeric_cols.append(col)
                    self.column_types[col] = 'numeric'

                self.column_profiles[col] = profile
                continue

            # ── 3. Categorical vs text ──
            n_unique_str = int(non_null.nunique())
            card_ratio = n_unique_str / n_non_null
            profile['n_unique'] = n_unique_str
            profile['cardinality_ratio'] = round(card_ratio, 3)

            # Check for mixed casing in low-cardinality columns
            if series.dtype == object and n_unique_str <= 60:
                sample = non_null.astype(str).head(200)
                upper_count = sample.str.isupper().sum()
                lower_count = sample.str.islower().sum()
                if upper_count > 0 and lower_count > 0 and (upper_count + lower_count) / max(len(sample), 1) > 0.3:
                    profile['mixed_format'] = True

            col_lower = col.lower()
            id_keywords_str = ['id', 'رقم', 'code', 'كود', 'رمز', 'no.', '#', 'num', 'name', 'اسم', 'بريد', 'email', 'phone', 'هاتف']

            if card_ratio > 0.8 and n_unique_str > 20:
                if any(kw in col_lower for kw in id_keywords_str):
                    profile['dtype'] = 'text'
                    profile['role'] = 'key'
                    self.key_cols.append(col)
                else:
                    profile['dtype'] = 'text'
                    profile['role'] = 'text'
                    self.text_cols.append(col)
                self.column_types[col] = 'text'
            elif n_unique_str <= 60 and card_ratio <= 0.6:
                profile['dtype'] = 'categorical'
                profile['role'] = 'dimension'
                self.dimension_cols.append(col)
                self.categorical_cols.append(col)
                self.column_types[col] = 'categorical'
            else:
                profile['dtype'] = 'text'
                profile['role'] = 'text'
                self.text_cols.append(col)
                self.column_types[col] = 'text'

            self.column_profiles[col] = profile

        return self.column_profiles

    # Backward compat alias
    def detect_column_types(self):
        return self.profile_columns()

    # =========================================================
    # STEP 2 — DERIVED METRIC DETECTION
    # =========================================================

    def detect_derived_metrics(self):
        """
        Step 2: Detect natural column combinations that produce more 
        meaningful business metrics than raw columns alone.

        Patterns detected:
          - unit_price × quantity → revenue (when no revenue column exists)
          - start_date → end_date → duration in days
        """
        self.derived_metrics = []

        def _kw_match(col_name, keywords):
            col_lower = col_name.lower()
            return any(kw.lower() in col_lower for kw in keywords)

        # Pattern A: Price × Quantity → Revenue
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

        # Pattern B: Start date → End date → Duration (days)
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

        return self.derived_metrics

    # =========================================================
    # STEP 3 — KPI GENERATOR (role-aware)
    # =========================================================

    def generate_kpis(self):
        """
        Step 3: Generate KPI cards using only statistically valid operations.

        Rules enforced:
          - Only measure columns (role='measure') get sum/avg/min/max
          - Key columns are NEVER used in calculations
          - Dimension columns auto-corrected to count instead of sum
          - Best/worst KPIs always name the ranking measure explicitly
          - Derived metrics are surfaced first as primary KPIs
          - KPIs with NaN or zero-from-all-nulls values are skipped
        """
        kpis = []

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

            kpi = self._validate_kpi({
                'label':    f"إجمالي {dm['name_short']} {dm['label_suffix']}",
                'value':    self._format_number(total),
                'raw_value': total,
                'kpi_type': 'derived',
                'icon':     dm.get('icon', 'calculator'),
                'color':    'success',
                'trend':    trend,
                'trend_value': trend_value,
            })
            if kpi:
                kpis.append(kpi)

            kpi_avg = self._validate_kpi({
                'label':    f"متوسط {dm['name_short']} {dm['label_suffix']}",
                'value':    self._format_number(avg),
                'raw_value': avg,
                'kpi_type': 'derived_avg',
                'icon':     'chart-bar',
                'color':    'info',
                'trend':    trend,
                'trend_value': trend_value,
            })
            if kpi_avg:
                kpis.append(kpi_avg)

        # ── Priority 2: Top measure columns ──
        priority_kw = [
            'مبيعات', 'إيرادات', 'ربح', 'تكلفة', 'سعر', 'كمية', 'عدد', 'مبلغ', 'قيمة', 'إجمالي',
            'sales', 'revenue', 'profit', 'cost', 'price', 'quantity', 'amount', 'total', 'score', 'value'
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

        for col, _, series in scored[:3]:
            total = float(series.sum())
            avg = float(series.mean())
            if total == 0 and avg == 0:
                continue
            trend, trend_value = self._calc_trend(self.df[col])

            kpi = self._validate_kpi({
                'label':    f'إجمالي {col}',
                'value':    self._format_number(total),
                'raw_value': total,
                'kpi_type': 'total',
                'icon':     'calculator',
                'color':    'primary',
                'trend':    trend,
                'trend_value': trend_value,
                'column':   col,
            })
            if kpi:
                kpis.append(kpi)

            kpi_avg = self._validate_kpi({
                'label':    f'متوسط {col}',
                'value':    self._format_number(avg),
                'raw_value': avg,
                'kpi_type': 'average',
                'icon':     'chart-bar',
                'color':    'info',
                'trend':    trend,
                'trend_value': trend_value,
                'column':   col,
            })
            if kpi_avg:
                kpis.append(kpi_avg)

        # ── Priority 3: Best / Worst dimension × measure ──
        if self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()

            # Prefer derived metric for ranking
            if self.derived_metrics:
                dm = self.derived_metrics[0]
                rank_series = dm['values']
                rank_label = dm['name_short']
            elif scored:
                rank_series = self.df[scored[0][0]]
                rank_label = scored[0][0]
            else:
                rank_series = None
                rank_label = None

            if dim_col and rank_series is not None:
                try:
                    temp = self.df[[dim_col]].copy()
                    temp['__v__'] = rank_series.values
                    grouped = temp.dropna().groupby(dim_col)['__v__'].sum().sort_values(ascending=False)
                    if len(grouped) >= 2:
                        top_name = str(grouped.index[0])
                        top_val  = float(grouped.iloc[0])
                        bot_name = str(grouped.index[-1])
                        bot_val  = float(grouped.iloc[-1])

                        kpi_best = self._validate_kpi({
                            'label':    f'أعلى {dim_col} (بإجمالي {rank_label})',
                            'value':    top_name,
                            'raw_value': top_val,
                            'subtitle': self._format_number(top_val),
                            'kpi_type': 'best',
                            'icon':     'trophy',
                            'color':    'success',
                            'trend':    'up',
                            'trend_value': 0,
                        })
                        if kpi_best:
                            kpis.append(kpi_best)

                        kpi_worst = self._validate_kpi({
                            'label':    f'أدنى {dim_col} (بإجمالي {rank_label})',
                            'value':    bot_name,
                            'raw_value': bot_val,
                            'subtitle': self._format_number(bot_val),
                            'kpi_type': 'worst',
                            'icon':     'arrow-down',
                            'color':    'danger',
                            'trend':    'down',
                            'trend_value': 0,
                        })
                        if kpi_worst:
                            kpis.append(kpi_worst)
                except Exception:
                    pass

        # ── Always: Record count ──
        kpi_count = self._validate_kpi({
            'label':    'إجمالي السجلات',
            'value':    f"{len(self.df):,}",
            'raw_value': len(self.df),
            'kpi_type': 'count',
            'icon':     'database',
            'color':    'secondary',
            'trend':    None,
            'trend_value': 0,
        })
        if kpi_count:
            kpis.append(kpi_count)

        return [k for k in kpis if k is not None][:8]

    # =========================================================
    # STEP 5 — KPI VALIDATOR (pre-render guard)
    # =========================================================

    def _validate_kpi(self, kpi):
        """
        Step 5: Validate a KPI before it is returned to the frontend.

        - Returns None  → KPI is invalid and should be skipped entirely
        - Returns kpi   → KPI is valid (possibly auto-corrected)
        - Auto-corrects dimension→count if sum/avg was requested on a dimension column
        - Skips KPIs with NaN raw_value
        """
        col = kpi.get('column')
        if col:
            profile = self.column_profiles.get(col, {})
            role = profile.get('role', 'measure')

            # Never render aggregations on key (ID) columns
            if role == 'key':
                return None

            # Auto-correct: sum/avg on dimension column → count instead
            if role == 'dimension' and kpi.get('kpi_type') in ('total', 'average'):
                count_val = self.df[col].nunique()
                kpi['label']     = f'عدد قيم {col} [تصحيح تلقائي]'
                kpi['value']     = str(count_val)
                kpi['raw_value'] = count_val
                kpi['icon']      = 'list'
                kpi['kpi_type']  = 'count'

        raw = kpi.get('raw_value')
        if raw is None:
            return None
        if isinstance(raw, float) and np.isnan(raw):
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
        """Calculate trend direction and percentage change (first half vs second half, sorted by date)."""
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
    # STEP 4 — DATA QUALITY (transparent, per-column)
    # =========================================================

    def assess_data_quality(self):
        """
        Step 4: Surface data quality issues transparently.

        Reports (never silently fixes):
          - Completeness score (overall)
          - Missing value breakdown by column (per column with ≥20% missing)
          - Duplicate rows
          - Constant columns (all_same = True) — useless for analysis
          - Low-confidence type inference
          - Mixed format columns (inconsistent values)
          - Outliers in measure columns
          - Key/ID columns that were excluded from calculations
        """
        issues = []
        details = {}
        total_cells = self.df.shape[0] * self.df.shape[1]

        # ── Missing values ──
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
                col: {
                    'count': int(cnt),
                    'percentage': round(cnt / len(self.df) * 100, 1),
                    'label': col,
                    'value': int(cnt),
                    'ratio': round(cnt / len(self.df) * 100, 1),
                }
                for col, cnt in missing_cols.items()
            }
            # Highlight individual columns with significant gaps
            for col, cnt in missing_cols.items():
                pct = round(cnt / len(self.df) * 100, 1)
                if pct >= 20:
                    issues.append({
                        'type': 'missing_column',
                        'severity': 'warning',
                        'message': f'عمود "{col}": {pct}% قيم مفقودة — مُستثنى من الحسابات',
                        'icon': 'minus-circle',
                        'affected_column': col,
                    })

        # ── Duplicate rows ──
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
            details['duplicate_count'] = dup_count

        # ── Constant columns (all values identical) ──
        for col, profile in self.column_profiles.items():
            if profile.get('all_same') and profile.get('role') not in ('key',):
                issues.append({
                    'type': 'constant_column',
                    'severity': 'info',
                    'message': f'عمود "{col}" يحتوي على قيمة واحدة فقط — لا يُفيد في التحليل',
                    'icon': 'ban',
                    'affected_column': col,
                })

        # ── Low confidence / mixed format columns ──
        for col, profile in self.column_profiles.items():
            if profile.get('confidence') == 'low':
                issues.append({
                    'type': 'ambiguous_type',
                    'severity': 'info',
                    'message': f'نوع عمود "{col}" غير محدد بثقة (تنسيق مختلط) — تم التعامل معه كنص',
                    'icon': 'question-circle',
                    'affected_column': col,
                })
            elif profile.get('mixed_format') and profile.get('confidence') != 'low':
                issues.append({
                    'type': 'mixed_format',
                    'severity': 'warning',
                    'message': f'عمود "{col}" يحتوي على تنسيقات متباينة (مثل مزيج أحرف كبيرة وصغيرة)',
                    'icon': 'random',
                    'affected_column': col,
                })

        # ── Outliers in measure columns ──
        outlier_info = {}
        for col in self.measure_cols:
            series = self.df[col].dropna()
            if len(series) < 10:
                continue
            Q1, Q3 = series.quantile(0.25), series.quantile(0.75)
            IQR = Q3 - Q1
            if IQR == 0:
                continue
            outlier_count = int(((series < Q1 - 1.5 * IQR) | (series > Q3 + 1.5 * IQR)).sum())
            if outlier_count > 0:
                outlier_info[col] = outlier_count

        if outlier_info:
            total_out = sum(outlier_info.values())
            cols_str = '، '.join(list(outlier_info.keys())[:3])
            issues.append({
                'type': 'outliers',
                'severity': 'info',
                'message': f'تم اكتشاف {total_out} قيمة شاذة في: {cols_str}',
                'icon': 'chart-line',
                'affected_column': None,
            })
            details['outliers_by_column'] = outlier_info

        # ── Key/ID columns excluded ──
        if self.key_cols:
            key_str = '، '.join(f'"{c}"' for c in self.key_cols[:4])
            issues.append({
                'type': 'keys_excluded',
                'severity': 'info',
                'message': f'الأعمدة التعريفية (مفاتيح) مُستبعدة من الحسابات: {key_str}',
                'icon': 'key',
                'affected_column': None,
            })

        # ── Completeness score ──
        completeness = round((1 - total_missing / total_cells) * 100, 1) if total_cells > 0 else 100.0

        if not issues:
            issues.append({
                'type': 'clean',
                'severity': 'success',
                'message': 'جودة البيانات ممتازة — لم يتم اكتشاف مشاكل',
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
            'derived_metric_count': len(self.derived_metrics),
        }

    # =========================================================
    # CHARTS (role-aware)
    # =========================================================

    def recommend_charts(self):
        """Generate charts using only role-appropriate column combinations."""
        charts = []
        used = set()

        # ── 1. Dimension × Measure → Bar Chart ──
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
                    combo = f'bar_{dim_col}_{measure_name}'
                else:
                    m_col = self._best_measure_col()
                    measure_name = m_col
                    suffix = ''
                    grouped = self.df.groupby(dim_col)[m_col].sum().sort_values(ascending=False).head(15) if m_col else None
                    combo = f'bar_{dim_col}_{m_col}'

                if combo not in used and grouped is not None and len(grouped) >= 2:
                    used.add(combo)
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'bar',
                        'title': f'إجمالي {measure_name} حسب {dim_col} {suffix}'.strip(),
                        'data': {
                            'labels': [str(x) for x in grouped.index.tolist()],
                            'datasets': [{
                                'label': f'إجمالي {measure_name}',
                                'data': [round(float(x), 2) for x in grouped.values.tolist()],
                                'backgroundColor': self._get_color_palette(len(grouped)),
                                'borderRadius': 6,
                            }]
                        },
                        'priority': 12
                    })

        # ── 2. Datetime × Measure → Line Chart ──
        if self.datetime_cols and (self.measure_cols or self.derived_metrics):
            dt_col = self.datetime_cols[0]
            measure_items = []
            for dm in self.derived_metrics:
                measure_items.append((dm['name_short'], dm['values'], dm['label_suffix']))
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

                    clean = [(i, v) for i, v in enumerate(values) if v is not None]
                    trendline = None
                    if len(clean) >= 3:
                        xa = np.array([p[0] for p in clean])
                        ya = np.array([p[1] for p in clean])
                        sl, ic, _, _, _ = stats.linregress(xa, ya)
                        trendline = [round(float(sl * i + ic), 2) for i in range(len(values))]

                    datasets = [{
                        'label': f'{m_name} {m_suffix}'.strip(),
                        'data': values,
                        'borderColor': '#4f46e5',
                        'backgroundColor': 'rgba(79, 70, 229, 0.1)',
                        'fill': True,
                        'tension': 0.4,
                        'pointRadius': 2,
                    }]
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
                        'title': f'اتجاه {m_name} عبر الزمن {m_suffix}'.strip(),
                        'data': {'labels': labels, 'datasets': datasets},
                        'priority': 9
                    })
                except Exception:
                    pass

        # ── 3. Dimension distribution → Doughnut ──
        if self.dimension_cols:
            dim_col = self._best_dimension_col()
            if dim_col:
                vc = self.df[dim_col].value_counts().head(8)
                if len(vc) >= 2:
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'doughnut',
                        'title': f'توزيع {dim_col}',
                        'data': {
                            'labels': [str(x) for x in vc.index.tolist()],
                            'datasets': [{
                                'data': [int(x) for x in vc.values.tolist()],
                                'backgroundColor': self._get_color_palette(len(vc)),
                                'borderWidth': 2,
                                'borderColor': '#ffffff',
                            }]
                        },
                        'priority': 7
                    })

        # ── 4. Two measure columns → Scatter ──
        if len(self.measure_cols) >= 2:
            col1, col2 = self.measure_cols[0], self.measure_cols[1]
            combo = f'scatter_{col1}_{col2}'
            if combo not in used:
                used.add(combo)
                temp = self.df[[col1, col2]].dropna()
                if len(temp) > 10:
                    if len(temp) > 500:
                        temp = temp.sample(500, random_state=42)
                    corr = temp[col1].corr(temp[col2])
                    corr_text = ''
                    if pd.notna(corr):
                        if abs(corr) > 0.7:
                            corr_text = f' — ارتباط {"طردي" if corr > 0 else "عكسي"} قوي ({round(corr, 2)})'
                        elif abs(corr) > 0.4:
                            corr_text = f' — ارتباط {"طردي" if corr > 0 else "عكسي"} متوسط ({round(corr, 2)})'
                    charts.append({
                        'id': f'chart_{len(charts)}',
                        'type': 'scatter',
                        'title': f'{col1} مقابل {col2}{corr_text}',
                        'data': {
                            'datasets': [{
                                'label': f'{col1} مقابل {col2}',
                                'data': [{'x': round(float(r[col1]), 2), 'y': round(float(r[col2]), 2)} for _, r in temp.iterrows()],
                                'backgroundColor': 'rgba(79, 70, 229, 0.5)',
                                'pointRadius': 4,
                            }]
                        },
                        'correlation': round(float(corr), 3) if pd.notna(corr) else None,
                        'priority': 6
                    })

        # ── 5. Measure histogram ──
        best_m = self._best_measure_col()
        if best_m:
            series = self.df[best_m].dropna()
            if len(series) >= 10:
                hist_vals, bin_edges = np.histogram(series, bins=min(20, max(5, len(series) // 10)))
                bin_labels = [f"{round(float(bin_edges[i]), 1)}–{round(float(bin_edges[i+1]), 1)}" for i in range(len(hist_vals))]
                charts.append({
                    'id': f'chart_{len(charts)}',
                    'type': 'bar',
                    'title': f'توزيع {best_m} (هستوغرام)',
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

        # ── 6. Two dimensions + measure → Grouped bar ──
        if len(self.dimension_cols) >= 2 and self.measure_cols:
            d1, d2 = self.dimension_cols[0], self.dimension_cols[1]
            m_col = self._best_measure_col()
            if m_col:
                try:
                    pivot = self.df.pivot_table(index=d1, columns=d2, values=m_col, aggfunc='sum').fillna(0)
                    if 2 <= pivot.shape[0] <= 15 and 2 <= pivot.shape[1] <= 8:
                        colors = self._get_color_palette(pivot.shape[1])
                        datasets = [{
                            'label': str(v),
                            'data': [round(float(x), 2) for x in pivot[v].values.tolist()],
                            'backgroundColor': colors[i % len(colors)],
                            'borderRadius': 4,
                        } for i, v in enumerate(pivot.columns)]
                        charts.append({
                            'id': f'chart_{len(charts)}',
                            'type': 'bar',
                            'title': f'إجمالي {m_col} حسب {d1} و {d2}',
                            'data': {'labels': [str(x) for x in pivot.index.tolist()], 'datasets': datasets},
                            'options': {'stacked': True},
                            'priority': 5
                        })
                except Exception:
                    pass

        charts.sort(key=lambda x: x.get('priority', 0), reverse=True)
        return charts[:8]

    # =========================================================
    # TREND DETECTION (measure-only)
    # =========================================================

    def detect_trends(self):
        """Detect trends and patterns — only on measure columns, never on keys."""
        trends = []

        if self.datetime_cols and (self.measure_cols or self.derived_metrics):
            dt_col = self.datetime_cols[0]
            measure_items = [(dm['name_short'], dm['values']) for dm in self.derived_metrics]
            for mc in self.measure_cols[:3]:
                measure_items.append((mc, self.df[mc]))

            for m_name, m_series in measure_items[:4]:
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
                            'message': f'{direction} في {m_name} بنسبة {abs(pct)}% خلال الفترة المحللة',
                            'r_squared': round(float(r_val ** 2), 3),
                            'significance': 'high' if p_val < 0.01 else 'medium'
                        })

                    n = len(y)
                    if n >= 10:
                        prev_mean = np.mean(y[:int(n * 0.9)])
                        rec_mean  = np.mean(y[int(n * 0.9):])
                        if prev_mean != 0:
                            change = (rec_mean - prev_mean) / abs(prev_mean) * 100
                            if abs(change) > 20:
                                trends.append({
                                    'type': 'spike' if change > 0 else 'drop',
                                    'column': m_name,
                                    'direction': 'up' if change > 0 else 'down',
                                    'message': f'تغير ملحوظ في {m_name} مؤخراً: {"ارتفاع" if change > 0 else "انخفاض"} بنسبة {abs(round(change, 1))}%',
                                    'significance': 'high'
                                })
                except Exception:
                    continue

        # Concentration: top-3 share of total (with explicit measure name)
        if self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()
            if self.derived_metrics:
                dm = self.derived_metrics[0]
                m_series = dm['values']
                m_name   = dm['name_short']
            else:
                m_col  = self._best_measure_col()
                m_series = self.df[m_col] if m_col else None
                m_name   = m_col

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
                            top_names = '، '.join([str(x) for x in top3.index[:3]])
                            trends.append({
                                'type': 'concentration',
                                'column': dim_col,
                                'direction': 'neutral',
                                'message': f'أعلى 3 من {dim_col} ({top_names}) تمثل {top_pct}% من إجمالي {m_name}',
                                'significance': 'high' if top_pct > 60 else 'medium'
                            })
                except Exception:
                    pass

        # Correlations (measure × measure only)
        if len(self.measure_cols) >= 2:
            for i in range(min(len(self.measure_cols), 4)):
                for j in range(i + 1, min(len(self.measure_cols), 4)):
                    col1, col2 = self.measure_cols[i], self.measure_cols[j]
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

    # =========================================================
    # NARRATIVE & INSIGHTS
    # =========================================================

    def generate_narrative(self, kpis, trends, quality):
        """Generate an Arabic executive summary (2–4 sentences)."""
        sentences = []
        rows, cols = len(self.df), len(self.df.columns)

        if self.derived_metrics:
            dm = self.derived_metrics[0]
            vals = dm['values'].dropna()
            total = self._format_number(float(vals.sum()))
            sentences.append(
                f'يحتوي الملف على {rows:,} سجل موزعة على {cols} عمود. '
                f'تم احتساب مقياس مشتق تلقائياً: {dm["name_short"]} بإجمالي {total}.'
            )
        elif self.measure_cols:
            best = self._best_measure_col()
            if best:
                series = self.df[best].dropna()
                total = self._format_number(float(series.sum()))
                avg   = self._format_number(float(series.mean()))
                sentences.append(
                    f'يحتوي الملف على {rows:,} سجل موزعة على {cols} عمود. '
                    f'إجمالي {best} يبلغ {total} بمتوسط {avg} لكل سجل.'
                )
        else:
            sentences.append(f'يحتوي الملف على {rows:,} سجل موزعة على {cols} عمود.')

        high_trends = [t for t in trends if t.get('significance') == 'high']
        if high_trends:
            sentences.append(high_trends[0]['message'] + '.')

        concentration = [t for t in trends if t['type'] == 'concentration']
        if concentration:
            sentences.append(concentration[0]['message'] + '.')

        if quality['completeness_score'] < 90:
            sentences.append(
                f'تنبيه: نسبة اكتمال البيانات {quality["completeness_score"]}% — '
                f'يُنصح بمراجعة القيم المفقودة لضمان دقة التحليل.'
            )

        if len(sentences) < 2 and self.dimension_cols and (self.measure_cols or self.derived_metrics):
            dim_col = self._best_dimension_col()
            m_col   = self._best_measure_col()
            if dim_col and m_col:
                try:
                    grouped = self.df.groupby(dim_col)[m_col].sum().sort_values(ascending=False)
                    if len(grouped) > 0:
                        top_name = str(grouped.index[0])
                        top_val  = self._format_number(float(grouped.iloc[0]))
                        sentences.append(
                            f'تتصدر "{top_name}" في {dim_col} بأعلى إجمالي {m_col} ({top_val}).'
                        )
                except Exception:
                    pass

        return ' '.join(sentences[:4])

    def generate_insights(self, trends, quality):
        """Generate actionable insights with explicit measure/dimension labels."""
        insights = []

        for trend in trends:
            if trend['type'] == 'trend' and trend['direction'] == 'up':
                insights.append({
                    'category': 'فرصة نمو',
                    'icon': 'arrow-up',
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
                    'category': 'تركيز',
                    'icon': 'info-circle',
                    'color': 'info',
                    'title': f'تركز عالٍ في {trend["column"]}',
                    'description': trend['message'] + '. قد يُشير هذا إلى اعتماد كبير على فئات محدودة.',
                    'priority': 'medium'
                })
            elif trend['type'] == 'correlation':
                insights.append({
                    'category': 'اكتشاف',
                    'icon': 'link',
                    'color': 'primary',
                    'title': f'ارتباط بين {trend["column"]}',
                    'description': trend['message'] + '. يمكن الاستفادة من هذه العلاقة في التنبؤ والتخطيط.',
                    'priority': 'medium'
                })
            elif trend['type'] in ('spike', 'drop'):
                insights.append({
                    'category': 'تنبيه مفاجئ',
                    'icon': 'bolt',
                    'color': 'warning',
                    'title': f'تغير مفاجئ في {trend["column"]}',
                    'description': trend['message'] + '. تحقق من الأسباب وراء هذا التغير.',
                    'priority': 'high'
                })

        for issue in quality.get('issues', []):
            if issue['type'] == 'missing' and issue['severity'] == 'danger':
                insights.append({
                    'category': 'جودة البيانات',
                    'icon': 'database',
                    'color': 'warning',
                    'title': 'نسبة مفقودات عالية',
                    'description': issue['message'] + '. يُنصح بمعالجة الفجوات قبل الاعتماد على النتائج.',
                    'priority': 'high'
                })
            elif issue['type'] == 'duplicates':
                insights.append({
                    'category': 'جودة البيانات',
                    'icon': 'copy',
                    'color': 'warning',
                    'title': 'صفوف مكررة',
                    'description': issue['message'],
                    'priority': 'medium'
                })
            elif issue['type'] == 'constant_column':
                insights.append({
                    'category': 'ملاحظة',
                    'icon': 'ban',
                    'color': 'info',
                    'title': f'عمود ثابت: {issue["affected_column"]}',
                    'description': issue['message'],
                    'priority': 'low'
                })

        if self.derived_metrics:
            for dm in self.derived_metrics:
                insights.append({
                    'category': 'مقياس محسوب',
                    'icon': 'calculator',
                    'color': 'primary',
                    'title': f'تم احتساب {dm["name_short"]} تلقائياً',
                    'description': f'صيغة الاحتساب: {dm["formula"]}. هذا المقياس يعكس القيمة الفعلية بدقة أكبر من الأعمدة المنفردة.',
                    'priority': 'medium'
                })

        if not insights:
            insights.append({
                'category': 'ملاحظة',
                'icon': 'check-circle',
                'color': 'success',
                'title': 'بيانات مستقرة',
                'description': 'لم يتم اكتشاف أنماط غير عادية. البيانات تبدو مستقرة ومتسقة.',
                'priority': 'low'
            })

        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 3))
        return insights

    # =========================================================
    # PIPELINE RUNNERS
    # =========================================================

    def run_full_analysis(self):
        """Run the complete 5-step analysis pipeline."""
        try:
            self.load_data()
            self.profile_columns()          # Step 1
            self.detect_derived_metrics()   # Step 2

            quality   = self.assess_data_quality()         # Step 4
            kpis      = self.generate_kpis()               # Step 3 + Step 5
            charts    = self.recommend_charts()
            trends    = self.detect_trends()
            narrative = self.generate_narrative(kpis, trends, quality)
            insights  = self.generate_insights(trends, quality)
            filters   = self._get_filter_options()

            return {
                'success': True,
                'analysis_mode': 'auto',
                'custom_query': '',
                'sheet_name': self.sheet_name,
                'row_count': len(self.df),
                'col_count': len(self.df.columns),
                'column_types': self.column_types,
                'columns': list(self.df.columns),
                'measure_cols': self.measure_cols,
                'dimension_cols': self.dimension_cols,
                'key_cols': self.key_cols,
                'derived_metrics': [
                    {'name': dm['name'], 'formula': dm['formula'], 'type': dm['type']}
                    for dm in self.derived_metrics
                ],
                'narrative': narrative,
                'quality':   quality,
                'kpis':      [k for k in kpis if k is not None],
                'charts':    charts,
                'trends':    trends,
                'insights':  insights,
                'filters':   filters,
            }
        except ValueError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f'خطأ غير متوقع: {str(e)}', 'trace': traceback.format_exc()}

    # =========================================================
    # CUSTOM ANALYSIS
    # =========================================================

    def _normalize_arabic(self, text):
        if not text:
            return ""
        text = str(text).lower()
        text = re.sub(r'[\u064B-\u065F]', '', text)
        text = re.sub(r'[أإآ]', 'ا', text)
        text = re.sub(r'ة', 'ه', text)
        text = re.sub(r'ى', 'ي', text)
        return text.strip()

    def _get_stems(self, word):
        w = self._normalize_arabic(word)
        stems = {w}
        if w.startswith('ال') and len(w) > 3:
            stems.add(w[2:])
        if 'فروع' in w or 'فرع' in w:
            stems.update(['فرع', 'فروع'])
        if 'مبيعات' in w or 'بيع' in w:
            stems.update(['مبيعات', 'بيع', 'ربح'])
        if 'منتجات' in w or 'منتج' in w or 'فئات' in w or 'فئه' in w:
            stems.update(['منتج', 'فئه', 'صنف', 'قسم'])
        if 'كميات' in w or 'كميه' in w:
            stems.update(['كميه', 'عدد'])
        if 'تكاليف' in w or 'تكلفه' in w:
            stems.update(['تكلفه', 'مصروف'])
        return stems

    def _match_query_to_columns(self, query_text):
        """Match query to columns — never matches key (ID) columns for aggregation."""
        norm_query = self._normalize_arabic(query_text)
        query_words = re.findall(r'\w+', norm_query)
        query_stems = set()
        for qw in query_words:
            query_stems.update(self._get_stems(qw))

        matched_numeric, matched_cat, matched_dt = [], [], []

        for col in self.df.columns:
            profile = self.column_profiles.get(col, {})
            role = profile.get('role', 'text')
            if role == 'key':
                continue  # Key columns never used in calculations

            col_stems = self._get_stems(col)
            is_match = bool(query_stems.intersection(col_stems))
            if not is_match:
                for qs in query_stems:
                    if len(qs) >= 3:
                        for cs in col_stems:
                            if len(cs) >= 3 and (qs in cs or cs in qs):
                                is_match = True
                                break
                    if is_match:
                        break

            if is_match:
                if role == 'measure' and col not in matched_numeric:
                    matched_numeric.append(col)
                elif role == 'dimension' and col not in matched_cat:
                    matched_cat.append(col)
                elif role == 'datetime' and col not in matched_dt:
                    matched_dt.append(col)

        return matched_numeric, matched_cat, matched_dt

    def run_custom_analysis(self, query_text):
        """Run analysis tailored to the user's custom query (Step 3 variant)."""
        try:
            self.load_data()
            self.profile_columns()
            self.detect_derived_metrics()

            if not query_text or not query_text.strip():
                return {'success': False, 'error': 'يرجى إدخال نص الطلب المخصص'}

            matched_num, matched_cat, matched_dt = self._match_query_to_columns(query_text)

            if not matched_num and not matched_cat and not matched_dt:
                # Offer only non-key columns as suggestions
                suggestions = [c for c in self.df.columns
                               if self.column_profiles.get(c, {}).get('role') != 'key']
                return {
                    'success': False,
                    'error_type': 'no_columns_matched',
                    'error': 'لم يتم العثور على أعمدة تطابق طلبك',
                    'query': query_text,
                    'suggestions': suggestions
                }

            # Apply time period from query text
            dt_col = matched_dt[0] if matched_dt else (self.datetime_cols[0] if self.datetime_cols else None)
            norm_q = self._normalize_arabic(query_text)
            if dt_col and dt_col in self.df.columns:
                try:
                    self.df[dt_col] = pd.to_datetime(self.df[dt_col], errors='coerce')
                    max_date = self.df[dt_col].max()
                    if pd.notna(max_date):
                        if '3 شهور' in norm_q or 'ثلاثه شهور' in norm_q or '3 اشهر' in norm_q:
                            self.df = self.df[self.df[dt_col] >= max_date - pd.DateOffset(months=3)]
                        elif '6 شهور' in norm_q or 'سته شهور' in norm_q:
                            self.df = self.df[self.df[dt_col] >= max_date - pd.DateOffset(months=6)]
                        elif 'شهر' in norm_q or '30 يوم' in norm_q:
                            self.df = self.df[self.df[dt_col] >= max_date - pd.DateOffset(months=1)]
                        elif 'سنه' in norm_q or 'عام' in norm_q:
                            self.df = self.df[self.df[dt_col] >= max_date - pd.DateOffset(years=1)]
                except Exception:
                    pass

            if self.df.empty:
                return {'success': False, 'error': 'لا توجد بيانات تطابق الفترة الزمنية المحددة في طلبك'}

            # Prioritize matched columns
            saved_m = self.measure_cols[:]
            saved_d = self.dimension_cols[:]
            if matched_num:
                self.measure_cols  = matched_num + [c for c in saved_m if c not in matched_num]
                self.numeric_cols  = self.measure_cols
            if matched_cat:
                self.dimension_cols   = matched_cat + [c for c in saved_d if c not in matched_cat]
                self.categorical_cols = self.dimension_cols

            quality   = self.assess_data_quality()
            kpis      = self.generate_kpis()
            charts    = self.recommend_charts()
            trends    = self.detect_trends()
            narrative = self._generate_custom_narrative(query_text, matched_num, matched_cat, kpis, trends)
            insights  = self.generate_insights(trends, quality)
            filters   = self._get_filter_options()

            # Restore
            self.measure_cols    = saved_m
            self.dimension_cols  = saved_d
            self.numeric_cols    = saved_m
            self.categorical_cols = saved_d

            return {
                'success': True,
                'analysis_mode': 'custom',
                'custom_query': query_text,
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
                'matched_columns': {
                    'numeric': matched_num,
                    'categorical': matched_cat,
                    'datetime': matched_dt
                }
            }
        except Exception as e:
            return {'success': False, 'error': f'خطأ في معالجة التحليل المخصص: {str(e)}'}

    def _generate_custom_narrative(self, query_text, matched_num, matched_cat, kpis, trends):
        sentences = [f'بناءً على طلبك المخصص ("{query_text}"):']
        main_num = matched_num[0] if matched_num else None
        main_cat = matched_cat[0] if matched_cat else None

        if main_num and main_num in self.df.columns:
            series = self.df[main_num].dropna()
            sentences.append(
                f'يبلغ إجمالي {main_num} {self._format_number(float(series.sum()))} '
                f'بمتوسط {self._format_number(float(series.mean()))} لكل سجل.'
            )

        if main_cat and main_num and main_cat in self.df.columns and main_num in self.df.columns:
            try:
                grouped = self.df.groupby(main_cat)[main_num].sum().sort_values(ascending=False)
                if len(grouped) > 0:
                    top_name = str(grouped.index[0])
                    top_val  = self._format_number(float(grouped.iloc[0]))
                    sentences.append(
                        f'تتصدر "{top_name}" كأعلى {main_cat} بإجمالي {main_num} يبلغ {top_val}.'
                    )
            except Exception:
                pass

        high = [t for t in trends if t.get('significance') == 'high']
        if high:
            sentences.append(high[0]['message'] + '.')

        return ' '.join(sentences[:4])

    def run_filtered_analysis(self, filters_dict):
        """Re-run analysis with applied date/category filters."""
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
        """
        Pick the most informative dimension column.
        Prefers genuine string/categorical columns over numeric-turned-dimension
        ones (e.g. region/category > rating 1-5), then ranks by unique count
        proximity to 8 (ideal for charts/KPIs).
        """
        best, best_score = None, -1
        for col in self.dimension_cols:
            profile = self.column_profiles.get(col, {})
            n = self.df[col].nunique()
            # Base score: closeness to ideal cardinality of 8
            score = 10 - abs(n - 8)
            if 3 <= n <= 20:
                score += 5
            # Strong bonus for genuine string/categorical columns
            if profile.get('dtype') == 'categorical':
                score += 8
            # Penalty for constant columns
            if profile.get('all_same'):
                score -= 20
            if score > best_score:
                best_score = score
                best = col
        return best or (self.dimension_cols[0] if self.dimension_cols else None)

    def _best_categorical_col(self):
        return self._best_dimension_col()

    def _best_measure_col(self):
        """Pick the most business-relevant measure column."""
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
