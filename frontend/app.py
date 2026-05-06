import time

import httpx
import streamlit as st

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="VibeUtopia", page_icon="🛡", layout="wide")

st.title("🛡 VibeUtopia - 发布前风控评估")
st.markdown("在发布文案前，模拟多平台用户反应，预测舆论风险，避免翻车。")

# ---- 侧边栏: 历史记录 ----
with st.sidebar:
    st.header("历史记录")
    try:
        resp = httpx.get(f"{API_BASE}/history", timeout=5)
        if resp.status_code == 200:
            history = resp.json()
            if history:
                for h in history[:10]:
                    score = h.get("overall_score", "-")
                    suggestion = h.get("suggestion", "")
                    status = h.get("status", "")
                    label = f"分数:{score} | {suggestion}" if status == "completed" else f"状态:{status}"
                    if st.button(label, key=h["task_id"]):
                        st.session_state["selected_task"] = h["task_id"]
            else:
                st.info("暂无历史记录")
        else:
            st.warning("无法加载历史记录")
    except Exception:
        st.warning("后端未启动")

# ---- 主区域: 输入 ----
tab_text, tab_video = st.tabs(["📝 文案输入", "🎬 视频链接"])

with tab_text:
    text_input = st.text_area("在此粘贴你的文案/脚本...", height=200, placeholder="输入至少10个字符的文案内容...", key="text_input")
    analyze_text_btn = st.button("🔍 开始评估", type="primary", use_container_width=True)

with tab_video:
    video_url = st.text_input("视频链接", placeholder="粘贴B站/抖音等视频链接...", key="video_url")
    col_extract, col_analyze = st.columns(2)
    with col_extract:
        extract_btn = st.button("📋 提取文案", use_container_width=True)
    with col_analyze:
        analyze_video_btn = st.button("🔍 提取并评估", type="primary", use_container_width=True)

    # 提取文案展示
    if extract_btn or analyze_video_btn:
        if not video_url:
            st.error("请输入视频链接")
        else:
            with st.spinner("正在提取视频文案..."):
                try:
                    resp = httpx.post(f"{API_BASE}/extract-video", json={"url": video_url}, timeout=30)
                    if resp.status_code == 200:
                        extract_data = resp.json()
                        st.success(f"提取成功 (来源: {extract_data.get('source', '未知')})")
                        st.markdown(f"**标题**: {extract_data.get('title', '')}")
                        if extract_data.get("subtitles"):
                            st.markdown(f"**字幕内容**:")
                            st.text(extract_data["subtitles"][:2000])
                        elif extract_data.get("description"):
                            st.markdown(f"**简介内容**:")
                            st.text(extract_data["description"][:2000])

                        if analyze_video_btn:
                            text_input = extract_data.get("text", "")
                            if len(text_input.strip()) < 10:
                                st.error("视频提取的文案太短，无法进行分析")
                            else:
                                resp = httpx.post(f"{API_BASE}/analyze", json={"text": text_input}, timeout=10)
                                if resp.status_code == 200:
                                    task_id = resp.json()["task_id"]
                                    st.session_state["current_task"] = task_id
                                    st.session_state.pop("analysis_result", None)
                                else:
                                    st.error(f"提交失败: {resp.text}")
                    else:
                        st.error(f"提取失败: {resp.text}")
                except Exception as e:
                    st.error(f"连接后端失败: {e}")

# 文案分析提交
if analyze_text_btn:
    if not text_input or len(text_input.strip()) < 10:
        st.error("请输入至少10个字符的文案")
    else:
        with st.spinner("正在提交分析..."):
            try:
                resp = httpx.post(f"{API_BASE}/analyze", json={"text": text_input}, timeout=10)
                if resp.status_code == 200:
                    task_id = resp.json()["task_id"]
                    st.session_state["current_task"] = task_id
                    st.session_state.pop("analysis_result", None)
                else:
                    st.error(f"提交失败: {resp.text}")
            except Exception as e:
                st.error(f"连接后端失败: {e}")

# ---- 轮询结果 ----
task_id = st.session_state.get("current_task") or st.session_state.get("selected_task")

if task_id and "analysis_result" not in st.session_state:
    progress_bar = st.progress(0, text="分析进行中...")
    result = None
    for i in range(60):
        progress_bar.progress(min(i / 60, 1.0), text=f"分析进行中... ({i * 2}s)")
        try:
            resp = httpx.get(f"{API_BASE}/analyze/{task_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data["status"] == "completed":
                    result = data
                    break
                elif data["status"] == "failed":
                    progress_bar.empty()
                    st.error("分析失败，请重试")
                    st.session_state.pop("current_task", None)
                    break
        except Exception:
            pass
        time.sleep(2)

    progress_bar.empty()

    if result:
        st.session_state["analysis_result"] = result
        st.session_state.pop("current_task", None)
        st.rerun()

# ---- 展示结果 ----
result = st.session_state.get("analysis_result") or st.session_state.get("selected_task_result")

if task_id and not result:
    # 从历史记录加载
    try:
        resp = httpx.get(f"{API_BASE}/analyze/{task_id}", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data["status"] == "completed":
                result = data
    except Exception:
        pass

if result:
    summary = result.get("summary", {})
    overall_score = summary.get("overall_score", 0)
    suggestion = summary.get("suggestion", "")
    risk_dimensions = summary.get("risk_dimensions", {})
    risk_items = result.get("risk_items", [])
    platform_reactions = result.get("platform_reactions", {})
    rewrites = result.get("rewrites", [])

    # 总分与建议
    st.divider()
    col_score, col_suggest = st.columns([1, 2])
    with col_score:
        score_color = "green" if overall_score <= 25 else ("orange" if overall_score <= 55 else "red")
        st.markdown(
            f'<div style="text-align:center;padding:20px;">'
            f'<span style="font-size:48px;font-weight:bold;color:{score_color}">{overall_score}</span>'
            f'<span style="font-size:24px;color:gray">/100</span></div>',
            unsafe_allow_html=True,
        )
    with col_suggest:
        suggest_icon = "✅" if suggestion == "可发" else ("⚠" if suggestion == "建议修改" else "🚫")
        st.markdown(f"### {suggest_icon} 发布建议: {suggestion}")

    # 七维风险 + 平台情绪
    col_radar, col_platform = st.columns(2)

    with col_radar:
        st.subheader("七维风险评估")
        if risk_dimensions:
            import pandas as pd
            dims = list(risk_dimensions.keys())
            scores = list(risk_dimensions.values())
            df = pd.DataFrame({"维度": dims, "分数": scores})
            st.dataframe(df, use_container_width=True, hide_index=True)

            for dim, score in risk_dimensions.items():
                color = "green" if score <= 20 else ("orange" if score <= 50 else "red")
                st.markdown(
                    f'**{dim}** '
                    f'<span style="color:{color}">{score}</span> '
                    f'<span style="background:{color};display:inline-block;width:{score}%;height:12px;border-radius:3px;"></span>',
                    unsafe_allow_html=True,
                )

    with col_platform:
        st.subheader("平台情绪预测")
        platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
        for platform_key, reaction in platform_reactions.items():
            name = platform_names.get(platform_key, platform_key)
            positive = reaction.get("positive", 0)
            neutral = reaction.get("neutral", 0)
            negative = reaction.get("negative", 0)
            reason = reaction.get("reason", "")

            st.markdown(f"**{name}**")
            pos_bar = f'<span style="background:green;display:inline-block;width:{positive*100}%;height:16px;border-radius:3px;"></span>'
            neu_bar = f'<span style="background:gray;display:inline-block;width:{neutral*100}%;height:16px;border-radius:3px;"></span>'
            neg_bar = f'<span style="background:red;display:inline-block;width:{negative*100}%;height:16px;border-radius:3px;"></span>'
            st.markdown(
                f'<div style="display:flex;gap:2px;">{pos_bar}{neu_bar}{neg_bar}</div>'
                f'<small>正面 {positive*100:.0f}% | 中性 {neutral*100:.0f}% | 负面 {negative*100:.0f}%</small>',
                unsafe_allow_html=True,
            )
            if reason:
                st.caption(f"原因: {reason}")

    # 句子级风险高亮
    if risk_items:
        st.divider()
        st.subheader("风险句子定位")
        for item in risk_items:
            severity_icon = "🔴" if item["severity"] == "high" else ("🟡" if item["severity"] == "medium" else "🟢")
            with st.expander(f'{severity_icon} {item["sentence"][:50]}...', expanded=(item["severity"] == "high")):
                st.markdown(f"**原句**: {item['sentence']}")
                st.markdown(f"**风险维度**: {item['dimension']}")
                st.markdown(f"**严重程度**: {item['severity']}")
                st.markdown(f"**判定依据**: {item['evidence']}")

    # 改写建议
    if rewrites:
        st.divider()
        st.subheader("安全改写建议")
        for rw in rewrites:
            original = rw.get("original", "")
            options = rw.get("rewrites", [])
            st.markdown(f"**原句**: {original}")
            for i, opt in enumerate(options, 1):
                st.success(f"改写{i}: {opt}")
            st.markdown("---")
