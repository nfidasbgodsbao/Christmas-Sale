import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="亚马逊圣诞销售进度看板", layout="wide")
st.title("🎄 亚马逊圣诞产品备货与销售进度看板")

# ================= 侧边栏：数据上传 =================
st.sidebar.header("📁 数据上传与管理")

# 1. 上传主数据表
uploaded_main = st.sidebar.file_uploader("1. 上传主数据表 (必须是 .xlsx 格式)", type=["xlsx"])
if uploaded_main:
    try:
        df_raw = pd.read_excel(uploaded_main, header=[0, 1])
        
        # 展平双层表头，并清理换行和空格
        df_raw.columns = [f"{str(col[0]).strip()}_{str(col[1]).strip()}" if "Unnamed" not in str(col[1]) else str(col[0]).strip() for col in df_raw.columns]
        
        # 核心逻辑：模糊匹配列名
        new_columns = {}
        for col in df_raw.columns:
            c_lower = col.lower()
            # 确保 '销售' 不会误匹配到 '销售员'、'总销售额' 等
            if '总备货' in c_lower:
                new_columns[col] = '总备货'
            elif '剩余库存' in c_lower:
                new_columns[col] = '剩余库存'
            elif '11月' in c_lower and '销量' in c_lower:
                new_columns[col] = '11月销量'
            elif 'asin' in c_lower:
                new_columns[col] = 'Asin'
            elif 'sku' in c_lower:
                new_columns[col] = 'SKU'
            elif '中文名称' in c_lower:
                new_columns[col] = '中文名称'
            elif '品类' in c_lower:
                new_columns[col] = '品类'
            elif '新旧品' in c_lower:
                new_columns[col] = '新旧品'
            elif '销售' in c_lower and '账号' not in c_lower and len(col) < 15: # 加上长度限制防止误判
                new_columns[col] = '销售'
        
        # 执行重命名
        df = df_raw.rename(columns=new_columns)
        
        # 🚨 关键防错：如果有多个列被映射成了相同的名字，只保留第一个
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 保留需要的核心列
        needed_cols = ['销售', 'SKU', '中文名称', 'Asin', '品类', '新旧品', '总备货', '剩余库存', '11月销量']
        existing_cols = [c for c in needed_cols if c in df.columns]
        df = df[existing_cols].copy()
        
        st.session_state['main_df'] = df
        st.sidebar.success("✅ 主数据已成功加载")
        
    except Exception as e:
        st.sidebar.error(f"读取文件失败，请检查表格格式。错误信息: {e}")

# ================= 处理11月数据更新 =================
uploaded_nov = st.sidebar.file_uploader("2. 上传11月实时销量表 (可选)", type=["xlsx"])
if uploaded_nov and 'main_df' in st.session_state:
    try:
        nov_df = pd.read_excel(uploaded_nov)
        nov_df.columns = [str(c).strip() for c in nov_df.columns]
        
        if 'Asin' in nov_df.columns and '11月' in nov_df.columns:
            nov_df = nov_df[['Asin', '11月']].rename(columns={'11月': '最新的11月销量'})
            # 合并更新
            st.session_state['main_df'] = pd.merge(st.session_state['main_df'], nov_df, on='Asin', how='left')
            st.session_state['main_df']['11月销量'] = st.session_state['main_df']['最新的11月销量'].combine_first(st.session_state['main_df'].get('11月销量', 0))
            st.session_state['main_df'] = st.session_state['main_df'].drop(columns=['最新的11月销量'])
            st.sidebar.success("🔄 11月数据已成功合并更新！")
        else:
            st.sidebar.warning("⚠️ 11月表格必须包含 'Asin' 和 '11月' 两列")
    except Exception as e:
        st.sidebar.error(f"11月数据合并失败: {e}")

# ================= 主面板逻辑 =================
if 'main_df' in st.session_state:
    df = st.session_state['main_df'].copy()
    
    # 数据清洗：确保数值列是数字类型
    for col in ['总备货', '剩余库存', '11月销量']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    
    # 填充文本列的缺失值
    for col in ['销售', '品类', '新旧品', '中文名称', 'SKU']:
        if col in df.columns:
            df[col] = df[col].fillna('未知')
            
    # ================= 筛选逻辑（修复版） =================
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 多维数据筛选")
    
    # 定义一个安全获取下拉列表的函数
    def get_options(df, column_name):
        if column_name in df.columns:
            vals = df[column_name].dropna().unique()
            # 过滤掉空字符串和异常值，并转成字符串排序
            clean_vals = [str(v) for v in vals if str(v).strip() not in ['', 'nan', 'None']]
            return ["全部"] + sorted(clean_vals)
        return ["全部"]

    sales_list = get_options(df, '销售')
    category_list = get_options(df, '品类')
    condition_list = get_options(df, '新旧品')

    sel_sales = st.sidebar.selectbox("销售员", sales_list)
    sel_category = st.sidebar.selectbox("品类", category_list)
    sel_condition = st.sidebar.selectbox("新旧品", condition_list)

    filtered_df = df.copy()
    if sel_sales != "全部" and '销售' in df.columns:
        filtered_df = filtered_df[filtered_df['销售'].astype(str) == sel_sales]
    if sel_category != "全部" and '品类' in df.columns:
        filtered_df = filtered_df[filtered_df['品类'].astype(str) == sel_category]
    if sel_condition != "全部" and '新旧品' in df.columns:
        filtered_df = filtered_df[filtered_df['新旧品'].astype(str) == sel_condition]

    # ================= 核心指标计算 =================
    total_inv = filtered_df['总备货'].sum() if '总备货' in filtered_df.columns else 0
    total_remain = filtered_df['剩余库存'].sum() if '剩余库存' in filtered_df.columns else 0
    sold_units = total_inv - total_remain
    calc_rate = (sold_units / total_inv * 100) if total_inv > 0 else 0

    # ================= 展示主面板 =================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 筛选后总备货", f"{int(total_inv):,}")
    col2.metric("🛒 累计已售出", f"{int(sold_units):,}")
    col3.metric("🏠 当前剩余库存", f"{int(total_remain):,}")
    col4.metric("📈 整体售出率进度", f"{calc_rate:.1f}%")
    
    if total_inv == 0:
        st.warning("⚠️ 当前筛选条件下总备货为 0，可能是该维度下没有数据，或者 Excel 表格里真的没有数字。")
    
    st.markdown("---")

    # ================= 图表与数据表展示 =================
    tab1, tab2, tab3 = st.tabs(["📊 品类售出率对比", "👤 销售业绩对比", "📄 详细明细数据"])
    
    with tab1:
        if '品类' in filtered_df.columns and total_inv > 0:
            cat_group = filtered_df.groupby('品类')[['总备货', '剩余库存']].sum().reset_index()
            cat_group['已售出'] = cat_group['总备货'] - cat_group['剩余库存']
            cat_group['售出率'] = (cat_group['已售出'] / cat_group['总备货'].replace(0, 1)) * 100
            
            fig_cat = px.bar(cat_group, x='品类', y='售出率', text='售出率',
                             title='各品类售出率进度 (%)',
                             color='售出率', color_continuous_scale='RdYlGn')
            fig_cat.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            st.plotly_chart(fig_cat, use_container_width=True)
            
    with tab2:
        if '销售' in filtered_df.columns and total_inv > 0:
            sales_group = filtered_df.groupby('销售')[['总备货', '剩余库存']].sum().reset_index()
            sales_group['已售出'] = sales_group['总备货'] - sales_group['剩余库存']
            
            fig_sales = px.bar(sales_group, x='销售', y=['已售出', '剩余库存'], 
                               title='各销售员备货与销售消耗情况', barmode='stack')
            st.plotly_chart(fig_sales, use_container_width=True)

    with tab3:
        st.write("💡 提示：您可以点击表头进行排序，找出售出率过低的产品。")
        show_cols = ['销售', 'SKU', '中文名称', '品类', '新旧品', '总备货', '剩余库存', '11月销量']
        available_cols = [c for c in show_cols if c in filtered_df.columns]
        
        display_df = filtered_df[available_cols].copy()
        
        # 计算单SKU售出率
        if '总备货' in display_df.columns and '剩余库存' in display_df.columns:
             display_df['单SKU售出率(%)'] = ((display_df['总备货'] - display_df['剩余库存']) / display_df['总备货'].replace(0, 1) * 100).round(1)
             cols = list(display_df.columns)
             if '单SKU售出率(%)' in cols:
                 cols.insert(5, cols.pop(cols.index('单SKU售出率(%)')))
                 display_df = display_df[cols]
             
        st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 请先在左侧上传你的主数据表 (必须是 .xlsx 格式)。")
