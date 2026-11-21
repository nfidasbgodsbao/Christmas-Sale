import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="亚马逊圣诞销售进度看板", layout="wide")
st.title("🎄 亚马逊圣诞产品备货与销售进度看板")

# ================= 侧边栏：数据上传 =================
st.sidebar.header("📁 数据上传与管理")

# 1. 上传主数据表（只在上传时处理）
uploaded_main = st.sidebar.file_uploader("1. 上传主数据表 (原始Excel文件)", type=["xlsx", "xls"])
if uploaded_main:
    st.session_state['main_df'] = pd.read_excel(uploaded_main, header=[0, 1])
    st.sidebar.success("✅ 主数据已加载")

# 2. 上传11月更新表
uploaded_nov = st.sidebar.file_uploader("2. 上传11月实时销量表", type=["xlsx", "xls"])

# ================= 数据预处理 =================
if 'main_df' in st.session_state:
    df = st.session_state['main_df'].copy()
    
    # 展平双层表头，并清理换行符
    df.columns = [f"{str(col[0]).strip()}_{str(col[1]).strip()}" if "Unnamed" not in str(col[1]) else str(col[0]).strip() for col in df.columns]
    
    # 重命名我们核心需要的列（确保对应你表格的准确列名）
    # 注意：这里的名字是根据你提供的文本推测的，如果报错找不到列，请核对实际Excel的列名
    rename_map = {
        '销售_Unnamed: 0_level_1': '销售',
        '账号_Unnamed: 0_level_1': '账号',
        'sku_Unnamed: 0_level_1': 'SKU',
        '中文名称_Unnamed: 0_level_1': '中文名称',
        'Asin_Unnamed: 0_level_1': 'Asin',
        '品类_Unnamed: 0_level_1': '品类',
        '新旧品_Unnamed: 0_level_1': '新旧品',
        '总备货(2026备货+FBA库存）_Unnamed: 0_level_1': '总备货',
        '2026剩余库存数_Unnamed: 0_level_1': '剩余库存',
        '售出率_Unnamed: 0_level_1': '总售出率',
        '销量_11月': '11月销量',
        '销量_12月': '12月销量'
    }
    
    # 安全替换（只替换存在的列）
    for old, new in rename_map.items():
        if old in df.columns:
            df = df.rename(columns={old: new})
        elif new not in df.columns and old.split('_')[0] in df.columns:
            # 兼容一些表头结构可能略有不同的情况
            pass

    # 确保数字列是数字类型
    for col in ['总备货', '剩余库存', '11月销量']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # ================= 处理11月数据更新 =================
    if uploaded_nov:
        nov_df = pd.read_excel(uploaded_nov)
        if 'Asin' in nov_df.columns and '11月' in nov_df.columns:
            # 合并更新 11月 销量
            nov_df = nov_df[['Asin', '11月']].rename(columns={'11月': '最新的11月销量'})
            df = pd.merge(df, nov_df, on='Asin', how='left')
            df['11月销量'] = df['最新的11月销量'].combine_first(df['11月销量'])
            df = df.drop(columns=['最新的11月销量'])
            st.sidebar.success("🔄 11月数据已成功合并更新！")
        else:
            st.sidebar.warning("⚠️ 上传的11月表格必须包含 'Asin' 和 '11月' 两列")

    # ================= 筛选逻辑 =================
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 多维数据筛选")
    
    sales_list = ["全部"] + list(df['销售'].dropna().unique()) if '销售' in df.columns else ["全部"]
    category_list = ["全部"] + list(df['品类'].dropna().unique()) if '品类' in df.columns else ["全部"]
    condition_list = ["全部"] + list(df['新旧品'].dropna().unique()) if '新旧品' in df.columns else ["全部"]

    sel_sales = st.sidebar.selectbox("销售员", sales_list)
    sel_category = st.sidebar.selectbox("品类", category_list)
    sel_condition = st.sidebar.selectbox("新旧品", condition_list)

    # 过滤数据
    filtered_df = df.copy()
    if sel_sales != "全部" and '销售' in df.columns:
        filtered_df = filtered_df[filtered_df['销售'] == sel_sales]
    if sel_category != "全部" and '品类' in df.columns:
        filtered_df = filtered_df[filtered_df['品类'] == sel_category]
    if sel_condition != "全部" and '新旧品' in df.columns:
        filtered_df = filtered_df[filtered_df['新旧品'] == sel_condition]

    # ================= 核心指标计算 =================
    total_inv = filtered_df['总备货'].sum() if '总备货' in filtered_df.columns else 0
    total_remain = filtered_df['剩余库存'].sum() if '剩余库存' in filtered_df.columns else 0
    sold_units = total_inv - total_remain
    
    # 计算当前动态售出率（已售 / 总备货）
    # 如果表格里自带售出率列，也可以直接用 '总售出率' 列的平均值
    calc_rate = (sold_units / total_inv * 100) if total_inv > 0 else 0

    # ================= 展示主面板 =================
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📦 筛选后总备货", f"{int(total_inv):,}")
    col2.metric("🛒 累计已售出", f"{int(sold_units):,}")
    col3.metric("🏠 当前剩余库存", f"{int(total_remain):,}")
    col4.metric("📈 整体售出率进度", f"{calc_rate:.1f}%")
    
    st.markdown("---")

    # ================= 图表与数据表展示 =================
    tab1, tab2, tab3 = st.tabs(["📊 品类售出率对比", "👤 销售业绩对比", "📄 详细明细数据"])
    
    with tab1:
        if '品类' in filtered_df.columns and total_inv > 0:
            cat_group = filtered_df.groupby('品类')[['总备货', '剩余库存']].sum().reset_index()
            cat_group['已售出'] = cat_group['总备货'] - cat_group['剩余库存']
            cat_group['售出率'] = (cat_group['已售出'] / cat_group['总备货']) * 100
            
            fig_cat = px.bar(cat_group, x='品类', y='售出率', text='售出率',
                             title='各品类售出率进度 (%)',
                             color='售出率', color_continuous_scale='RdYlGn')
            fig_cat.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            st.plotly_chart(fig_cat, use_container_width=True)
            
    with tab2:
        if '销售' in filtered_df.columns and total_inv > 0:
            sales_group = filtered_df.groupby('销售')[['总备货', '剩余库存']].sum().reset_index()
            sales_group['已售出'] = sales_group['总备货'] - sales_group['剩余库存']
            sales_group['售出率'] = (sales_group['已售出'] / sales_group['总备货']) * 100
            
            fig_sales = px.bar(sales_group, x='销售', y=['已售出', '剩余库存'], 
                               title='各销售员备货与销售消耗情况', barmode='stack')
            st.plotly_chart(fig_sales, use_container_width=True)

    with tab3:
        st.write("💡 提示：您可以在这里点击表头进行排序，查看哪些SKU进度过慢。")
        # 选取想要展示的列
        show_cols = ['销售', 'SKU', '中文名称', '品类', '总备货', '剩余库存', '11月销量']
        available_cols = [c for c in show_cols if c in filtered_df.columns]
        
        # 格式化显示
        display_df = filtered_df[available_cols].copy()
        if '总备货' in display_df.columns and '剩余库存' in display_df.columns:
             display_df['单SKU售出率(%)'] = ((display_df['总备货'] - display_df['剩余库存']) / display_df['总备货'].replace(0, 1) * 100).round(1)
             
        st.dataframe(display_df, use_container_width=True, hide_index=True)

else:
    st.info("👈 请先在左侧上传你的原始 Excel 数据表，系统将自动生成图表。")
