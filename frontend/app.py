import json
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
tab_text, tab_video, tab_signal, tab_graph, tab_persona = st.tabs(["📝 文案输入", "🎬 视频链接", "📡 信号采集", "🕸 知识图谱", "🧬 人格工厂"])

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
    transcript_quality = summary.get("transcript_quality")
    dimension_weights = summary.get("dimension_weights")
    cross_effects = summary.get("cross_effects", [])

    agents = summary.get("agents", [])

    # 转写质量警告横幅（新增）
    if transcript_quality and transcript_quality.get("quality_level") not in ("clean", None):
        tq_level = transcript_quality.get("quality_level", "")
        tq_score = transcript_quality.get("quality_score", 100)
        tq_hints = transcript_quality.get("transcript_hints", [])
        noise_count = len(transcript_quality.get("noise_sentences", []))

        if tq_level == "garbled":
            st.error(f"⚠️ **转写质量极差** (分数: {tq_score}/100) — {'; '.join(tq_hints)} | 检测到{noise_count}处疑似转写错误，部分风险评估可能不准确")
        elif tq_level == "heavy_noise":
            st.warning(f"⚠️ **转写质量较差** (分数: {tq_score}/100) — {'; '.join(tq_hints)} | 检测到{noise_count}处疑似转写错误，部分风险判定可能受影响")
        elif tq_level == "light_noise":
            st.info(f"ℹ️ **转写质量一般** (分数: {tq_score}/100) — {'; '.join(tq_hints)}")

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

    # 交叉风险提示（新增）
    if cross_effects:
        for ce in cross_effects:
            dims = ce.get("dimensions", [])
            desc = ce.get("description", "")
            combined_sev = ce.get("combined_severity", "medium")
            icon = "🔴" if combined_sev == "high" else "🟡"
            st.markdown(f"{icon} **交叉风险**: {' + '.join(dims)} — {desc}")

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
                # 展示维度权重标签（新增）
                weight_label = ""
                if dimension_weights and dim in dimension_weights:
                    w = dimension_weights[dim]
                    if w > 1.0:
                        weight_label = f' <span style="color:red;font-size:0.8em">[权重×{w}]</span>'
                st.markdown(
                    f'**{dim}** '
                    f'<span style="color:{color}">{score}</span>{weight_label} '
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
                # 解析群体分化信息（新增）
                reason_lines = reason.split("\n")
                main_reason = reason_lines[0]
                st.caption(f"原因: {main_reason}")
                for line in reason_lines[1:]:
                    if line.startswith("[群体分化]"):
                        with st.expander("查看群体分化详情"):
                            groups = line.replace("[群体分化] ", "").split("; ")
                            for g in groups:
                                st.markdown(f"- {g.strip()}")
                    elif line.startswith("[Agent反应]"):
                        with st.expander("查看Agent个体反应"):
                            agent_reactions = line.replace("[Agent反应] ", "").split("; ")
                            for ar in agent_reactions:
                                st.markdown(f"- {ar.strip()}")

    # 句子级风险高亮
    if risk_items:
        st.divider()
        st.subheader("风险句子定位")
        for item in risk_items:
            severity_icon = "🔴" if item["severity"] == "high" else ("🟡" if item["severity"] == "medium" else "🟢")
            affected = item.get("affected_groups", [])
            affected_label = f" | 影响群体: {', '.join(affected)}" if affected else ""
            with st.expander(f'{severity_icon} {item["sentence"][:50]}...{affected_label}', expanded=(item["severity"] == "high")):
                st.markdown(f"**原句**: {item['sentence']}")
                st.markdown(f"**风险维度**: {item['dimension']}")
                st.markdown(f"**严重程度**: {item['severity']}")
                st.markdown(f"**判定依据**: {item['evidence']}")
                if affected:
                    st.markdown(f"**影响群体**: {', '.join(affected)}")
                dim_w = item.get("dimension_weight")
                if dim_w and dim_w > 1.0:
                    st.markdown(f"**维度权重**: ×{dim_w} (高风险维度加权)")

    # 改写建议
    if rewrites:
        st.divider()
        st.subheader("安全改写建议")
        for rw in rewrites:
            original = rw.get("original", "")
            is_noise = rw.get("is_transcript_noise", False)
            transcript_note = rw.get("transcript_note", "")
            options = rw.get("rewrites", [])

            st.markdown(f"**原句**: {original}")

            if is_noise:
                # 转写噪声标注（新增）
                st.info(f"📋 **转写质量问题**: {transcript_note}")
            elif options:
                for i, opt in enumerate(options, 1):
                    st.success(f"改写{i}: {opt}")
            st.markdown("---")

    # Agent视角展示（新增）
    if agents:
        st.divider()
        st.subheader("Agent视角洞察")
        st.caption(f"共 {len(agents)} 个差异化Agent参与了本次模拟")

        # 按平台分组展示
        platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
        platform_groups = {}
        for agent in agents:
            p = agent.get("platform", "unknown")
            if p not in platform_groups:
                platform_groups[p] = []
            platform_groups[p].append(agent)

        for platform_key, platform_agents in platform_groups.items():
            p_name = platform_names.get(platform_key, platform_key)
            with st.expander(f"📱 {p_name} — {len(platform_agents)}个Agent", expanded=False):
                for agent in platform_agents:
                    reaction_type = agent.get("reaction_type", "neutral")
                    reaction_icon = "👍" if reaction_type == "positive" else ("😐" if reaction_type == "neutral" else "👎")
                    intensity = agent.get("emotional_intensity", 0)
                    persona_name = agent.get("persona_name", "匿名用户")
                    archetype = agent.get("archetype", "")
                    comment = agent.get("comment", "")
                    focus = agent.get("focus", "")
                    reasoning = agent.get("reasoning", "")

                    col_icon, col_content = st.columns([1, 10])
                    with col_icon:
                        st.markdown(f"**{reaction_icon}**")
                    with col_content:
                        st.markdown(f"**{persona_name}** ({archetype}) — 情感强度: {intensity:.1f}")
                        if comment:
                            st.markdown(f"> {comment}")
                        if focus:
                            st.caption(f"关注点: {focus}")
                        if reasoning:
                            with st.expander("内心推理"):
                                st.markdown(reasoning)
                    st.markdown("---")

# ---- 信号采集 Tab ----
with tab_signal:
    st.subheader("📡 信号采集控制台")

    # 调度器状态与控制
    col_ctrl, col_status = st.columns([1, 1])

    with col_ctrl:
        st.markdown("**调度模式**")
        schedule_mode = st.radio(
            "选择调度模式",
            ["standard", "realtime", "economy", "manual"],
            format_func=lambda x: {
                "realtime": "🔴 实时监控 (5分钟/次)",
                "standard": "🟡 标准模式 (10分钟/次)",
                "economy": "🟢 经济模式 (30分钟/次)",
                "manual": "⚪ 手动模式",
            }[x],
            horizontal=True,
            key="schedule_mode",
        )

        col_start, col_stop = st.columns(2)
        with col_start:
            if st.button("▶ 启动调度", type="primary", use_container_width=True):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/signals/scheduler",
                        json={"action": "start", "mode": schedule_mode},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"调度已启动，模式: {data.get('mode', 'unknown')}")
                    else:
                        st.error(f"启动失败: {resp.text}")
                except Exception as e:
                    st.error(f"连接失败: {e}")

        with col_stop:
            if st.button("⏹ 停止调度", use_container_width=True):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/signals/scheduler",
                        json={"action": "stop"},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        st.success("调度已停止")
                    else:
                        st.error(f"停止失败: {resp.text}")
                except Exception as e:
                    st.error(f"连接失败: {e}")

    with col_status:
        st.markdown("**当前状态**")
        st.info("调度器默认为手动模式，点击"启动调度"开始自动采集")

    # 手动爬取
    st.divider()
    st.markdown("**手动深度爬取**")
    col_kw, col_plat = st.columns([2, 1])
    with col_kw:
        manual_keyword = st.text_input("搜索关键词", placeholder="输入关键词手动爬取评论...", key="manual_keyword")
    with col_plat:
        manual_platforms = st.multiselect("搜索平台", ["微博", "知乎", "B站"], default=["微博", "知乎"], key="manual_platforms")

    if st.button("🔍 手动爬取评论", key="manual_crawl_btn"):
        if not manual_keyword:
            st.error("请输入关键词")
        else:
            with st.spinner(f"正在爬取 '{manual_keyword}' 的评论..."):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/signals/crawl",
                        json={"keyword": manual_keyword, "platforms": manual_platforms},
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        count = data.get("comments_count", 0)
                        st.success(f"爬取完成，共 {count} 条评论")
                        comments = data.get("comments", [])
                        if comments:
                            import pandas as pd
                            df = pd.DataFrame(comments)
                            st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.error(f"爬取失败: {resp.text}")
                except Exception as e:
                    st.error(f"连接失败: {e}")

    # 热榜数据展示
    st.divider()
    st.subheader("📊 各平台热榜")

    if st.button("🔄 刷新热榜", key="refresh_hotlist"):
        st.session_state.pop("hotlist_data", None)

    hotlist_data = st.session_state.get("hotlist_data")
    if hotlist_data is None:
        try:
            resp = httpx.get(f"{API_BASE}/signals/hot", params={"limit": 10}, timeout=10)
            if resp.status_code == 200:
                hotlist_data = resp.json().get("platforms", {})
                st.session_state["hotlist_data"] = hotlist_data
        except Exception:
            hotlist_data = {}

    if hotlist_data:
        # 按平台分组展示
        cols = st.columns(min(len(hotlist_data), 4))
        for idx, (platform_name, items) in enumerate(hotlist_data.items()):
            col_idx = idx % len(cols)
            with cols[col_idx]:
                with st.expander(f"📱 {platform_name} ({len(items)}条)", expanded=(idx < 2)):
                    for item in items[:10]:
                        rank = item.get("rank", "-")
                        title = item.get("title", "")
                        is_new = item.get("is_new", False)
                        new_tag = " 🆕" if is_new else ""
                        url = item.get("url")
                        if url:
                            st.markdown(f"{rank}. [{title}]({url}){new_tag}")
                        else:
                            st.markdown(f"{rank}. {title}{new_tag}")
    else:
        st.info("暂无热榜数据，请启动调度器或等待采集")

    # 种子事件列表
    st.divider()
    st.subheader("🌱 种子事件")

    if st.button("🔄 刷新事件", key="refresh_events"):
        st.session_state.pop("events_data", None)

    events_data = st.session_state.get("events_data")
    if events_data is None:
        try:
            resp = httpx.get(f"{API_BASE}/signals/events", params={"limit": 20}, timeout=10)
            if resp.status_code == 200:
                events_data = resp.json()
                st.session_state["events_data"] = events_data
        except Exception:
            events_data = {"total": 0, "events": []}

    total_events = events_data.get("total", 0)
    events_list = events_data.get("events", [])

    if events_list:
        st.caption(f"共 {total_events} 个种子事件")
        for event in events_list:
            strength = event.get("signal_strength", 0)
            strength_pct = int(strength * 100)
            strength_color = "green" if strength < 0.4 else ("orange" if strength < 0.7 else "red")
            category = event.get("category", "")
            crawl_depth = event.get("crawl_depth", "none")
            depth_icon = "🔍" if crawl_depth == "deep" else ("🔎" if crawl_depth == "shallow" else "")

            with st.expander(
                f"{depth_icon} [{category}] {event['title']} — 强度 {strength_pct}%",
                expanded=(strength >= 0.7),
            ):
                col_detail, col_strength = st.columns([3, 1])
                with col_detail:
                    st.markdown(f"**分类**: {category}")
                    st.markdown(f"**来源平台**: {', '.join(event.get('source_platforms', []))}")
                    st.markdown(f"**爬取深度**: {crawl_depth}")
                    st.markdown(f"**创建时间**: {event.get('created_at', '未知')}")
                with col_strength:
                    st.markdown(
                        f'<div style="text-align:center;padding:10px;">'
                        f'<span style="font-size:28px;font-weight:bold;color:{strength_color}">{strength_pct}%</span>'
                        f'<br><small>信号强度</small></div>',
                        unsafe_allow_html=True,
                    )
    else:
        st.info("暂无种子事件，请启动调度器并等待事件检测")

# ---- 知识图谱 Tab ----
with tab_graph:
    st.subheader("🕸 知识图谱")

    # 图谱统计
    col_stats, col_action = st.columns([1, 1])

    with col_stats:
        st.markdown("**图谱状态**")
        try:
            resp = httpx.get(f"{API_BASE}/graph/stats", timeout=5)
            if resp.status_code == 200:
                stats = resp.json()
                if stats.get("connected"):
                    st.success(f"Neo4j 已连接 | 节点: {stats.get('node_count', 0)} | 关系: {stats.get('relation_count', 0)}")
                    labels = stats.get("labels", [])
                    if labels:
                        st.caption(f"实体类型: {', '.join(labels)}")
                else:
                    st.warning("Neo4j 未连接，图谱功能不可用（需启动 Docker Neo4j 服务）")
            else:
                st.warning("图谱服务不可用")
        except Exception:
            st.warning("后端未启动")

    with col_action:
        st.markdown("**实体抽取**")
        extract_title = st.text_input("事件标题", placeholder="输入事件标题进行实体抽取...", key="graph_extract_title")
        extract_desc = st.text_area("事件描述", placeholder="可选：输入事件详细描述...", height=80, key="graph_extract_desc")

        if st.button("🔍 抽取实体", type="primary", key="graph_extract_btn"):
            if not extract_title:
                st.error("请输入事件标题")
            else:
                with st.spinner("正在抽取实体和关系..."):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/graph/extract",
                            json={"title": extract_title, "description": extract_desc},
                            timeout=60,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            entities = data.get("entities", [])
                            relations = data.get("relations", [])
                            st.success(f"抽取完成: {len(entities)} 个实体, {len(relations)} 个关系")

                            if entities:
                                import pandas as pd
                                df = pd.DataFrame([
                                    {"名称": e["name"], "类型": e["entity_type"], "ID": e["entity_id"][:8] + "..."}
                                    for e in entities
                                ])
                                st.dataframe(df, use_container_width=True, hide_index=True)

                            if relations:
                                for r in relations:
                                    st.markdown(f"- **{r['relation_type']}**: {r['source_id'][:8]}... → {r['target_id'][:8]}... (权重: {r['weight']:.2f})")
                        else:
                            st.error(f"抽取失败: {resp.text}")
                    except Exception as e:
                        st.error(f"连接失败: {e}")

    # 本体查看
    st.divider()
    col_ont, col_query = st.columns([1, 1])

    with col_ont:
        st.markdown("**图谱本体**")
        try:
            resp = httpx.get(f"{API_BASE}/graph/ontology", timeout=5)
            if resp.status_code == 200:
                ontology = resp.json()
                entity_types = ontology.get("entity_types", [])
                relation_types = ontology.get("relation_types", [])

                with st.expander(f"📋 实体类型 ({len(entity_types)})", expanded=True):
                    for et in entity_types:
                        props = ", ".join(et.get("properties", []))
                        st.markdown(f"- **{et['name']}**: {et['description']} ({props})")

                with st.expander(f"🔗 关系类型 ({len(relation_types)})", expanded=False):
                    for rt in relation_types:
                        st.markdown(f"- **{rt['name']}** ({rt['source']} → {rt['target']}): {rt['description']}")
            else:
                st.info("无法加载本体定义")
        except Exception:
            st.info("后端未启动")

    with col_query:
        st.markdown("**子图查询**")
        query_entity_id = st.text_input("中心实体ID", placeholder="输入实体ID查询子图...", key="graph_query_id")
        query_depth = st.slider("展开深度", 1, 4, 2, key="graph_query_depth")

        if st.button("🔎 查询子图", key="graph_query_btn"):
            if not query_entity_id:
                st.error("请输入实体ID")
            else:
                with st.spinner("正在查询子图..."):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/graph/query",
                            json={"entity_id": query_entity_id, "depth": query_depth},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            subgraph = resp.json()
                            nodes = subgraph.get("nodes", [])
                            edges = subgraph.get("edges", [])
                            st.success(f"查询完成: {len(nodes)} 个节点, {len(edges)} 条边")

                            if nodes:
                                import pandas as pd
                                df = pd.DataFrame(nodes)
                                st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            st.error(f"查询失败: {resp.text}")
                    except Exception as e:
                        st.error(f"连接失败: {e}")

    # 从种子事件批量构建图谱
    st.divider()
    st.markdown("**从种子事件构建图谱**")
    col_events, col_build = st.columns([2, 1])

    with col_events:
        try:
            resp = httpx.get(f"{API_BASE}/signals/events", params={"limit": 10, "status": "active"}, timeout=10)
            if resp.status_code == 200:
                events = resp.json().get("events", [])
                if events:
                    event_options = {e["event_id"]: e["title"] for e in events}
                    selected_events = st.multiselect(
                        "选择种子事件",
                        options=list(event_options.keys()),
                        format_func=lambda x: event_options[x][:50],
                        key="graph_event_select",
                    )
                else:
                    st.info("暂无活跃种子事件")
                    selected_events = []
            else:
                selected_events = []
        except Exception:
            selected_events = []

    with col_build:
        if st.button("🔨 批量构建图谱", type="primary", key="graph_build_btn"):
            if not selected_events:
                st.error("请选择至少一个种子事件")
            else:
                progress = st.progress(0, text="正在构建图谱...")
                total = len(selected_events)
                success_count = 0

                for i, event_id in enumerate(selected_events):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/graph/extract",
                            json={"event_id": event_id},
                            timeout=60,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("status") == "completed":
                                success_count += 1
                    except Exception:
                        pass
                    progress.progress((i + 1) / total, text=f"处理中... {i+1}/{total}")

                progress.empty()
                st.success(f"图谱构建完成: {success_count}/{total} 个事件处理成功")

# ---- 人格工厂 Tab ----
with tab_persona:
    st.subheader("🧬 人格工厂")

    # 统计概览
    col_stats, col_gen = st.columns([1, 1])

    with col_stats:
        st.markdown("**Agent统计**")
        try:
            resp = httpx.get(f"{API_BASE}/agents/stats", timeout=5)
            if resp.status_code == 200:
                stats = resp.json()
                total = stats.get("total_agents", 0)
                avg_q = stats.get("avg_quality_score", 0)
                rels = stats.get("total_relations", 0)
                mems = stats.get("total_memories", 0)
                st.metric("活跃Agent", total)
                st.metric("平均质量分", f"{avg_q:.2f}")
                st.caption(f"社会关系: {rels} 条 | 记忆: {mems} 条")

                by_platform = stats.get("by_platform", {})
                if by_platform:
                    platform_names = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}
                    plat_text = " | ".join(f"{platform_names.get(k, k)}: {v}" for k, v in by_platform.items())
                    st.caption(plat_text)
            else:
                st.info("Agent服务不可用")
        except Exception:
            st.warning("后端未启动")

    with col_gen:
        st.markdown("**生成Agent**")
        gen_platforms = st.multiselect(
            "目标平台",
            ["bilibili", "xiaohongshu", "zhihu", "douyin"],
            default=["bilibili", "xiaohongshu", "zhihu", "douyin"],
            format_func=lambda x: {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}.get(x, x),
            key="gen_platforms",
        )
        gen_count = st.slider("每平台数量", 1, 20, 5, key="gen_count")
        gen_graph = st.checkbox("注入知识图谱", value=False, key="gen_graph")

        if st.button("🔨 生成Agent", type="primary", key="gen_agent_btn"):
            if not gen_platforms:
                st.error("请选择至少一个平台")
            else:
                with st.spinner(f"正在生成 {len(gen_platforms)} × {gen_count} = {len(gen_platforms)*gen_count} 个Agent..."):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/agents/generate",
                            json={
                                "platforms": gen_platforms,
                                "count_per_platform": gen_count,
                                "inject_graph": gen_graph,
                                "persist": True,
                            },
                            timeout=300,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.success(f"生成完成: {data.get('total_agents', 0)} 个Agent")
                            by_plat = data.get("by_platform", {})
                            for p, c in by_plat.items():
                                pn = {"bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}.get(p, p)
                                st.caption(f"{pn}: {c} 个")
                        else:
                            st.error(f"生成失败: {resp.text}")
                    except Exception as e:
                        st.error(f"连接失败: {e}")

    # Agent列表
    st.divider()
    st.subheader("📋 Agent列表")

    col_filter, col_search = st.columns([1, 2])
    with col_filter:
        filter_platform = st.selectbox(
            "平台筛选",
            ["全部", "bilibili", "xiaohongshu", "zhihu", "douyin"],
            format_func=lambda x: {"全部": "全部", "bilibili": "B站", "xiaohongshu": "小红书", "zhihu": "知乎", "douyin": "抖音"}.get(x, x),
            key="filter_platform",
        )
    with col_search:
        filter_archetype = st.text_input("原型筛选", placeholder="输入原型ID关键词...", key="filter_archetype")

    if st.button("🔄 刷新列表", key="refresh_agents"):
        st.session_state.pop("agents_list", None)

    agents_data = st.session_state.get("agents_list")
    if agents_data is None:
        try:
            params = {"limit": 50, "status": "active"}
            if filter_platform != "全部":
                params["platform"] = filter_platform
            if filter_archetype:
                params["archetype"] = filter_archetype
            resp = httpx.get(f"{API_BASE}/agents", params=params, timeout=10)
            if resp.status_code == 200:
                agents_data = resp.json()
                st.session_state["agents_list"] = agents_data
        except Exception:
            agents_data = {"total": 0, "agents": []}

    total_agents = agents_data.get("total", 0)
    agents_list = agents_data.get("agents", [])

    if agents_list:
        st.caption(f"共 {total_agents} 个活跃Agent")
        import pandas as pd
        df = pd.DataFrame(agents_list)
        display_cols = ["agent_id", "platform", "archetype_base", "quality_score", "name"]
        available_cols = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("暂无Agent，请先生成")

    # Agent详情查看
    st.divider()
    st.markdown("**查看Agent详情**")
    detail_agent_id = st.text_input("输入Agent ID", placeholder="从列表中选择Agent ID...", key="detail_agent_id")

    if st.button("🔎 查看详情", key="view_agent_btn"):
        if not detail_agent_id:
            st.error("请输入Agent ID")
        else:
            try:
                resp = httpx.get(f"{API_BASE}/agents/{detail_agent_id}", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    persona = data.get("persona", {})

                    st.markdown(f"### {persona.get('L1_basic', {}).get('occupation', '未知')} ({data.get('platform', '')})")
                    st.caption(f"原型: {data.get('archetype_base', '')} | 质量分: {data.get('quality_score', 0):.2f} | 版本: v{data.get('version', 1)}")

                    # 7层人格展示
                    layer_names = {
                        "L1_basic": "L1 基础属性",
                        "L2_values": "L2 价值观",
                        "L3_knowledge": "L3 知识背景",
                        "L4_behavior": "L4 行为模式",
                        "L5_correction": "L5 校正层",
                        "L6_social": "L6 社交关系",
                        "L7_evolution": "L7 动态演化",
                    }
                    for layer_key, layer_name in layer_names.items():
                        layer_data = persona.get(layer_key, {})
                        if layer_data:
                            with st.expander(layer_name, expanded=(layer_key in ("L1_basic", "L2_values"))):
                                if isinstance(layer_data, dict):
                                    for k, v in layer_data.items():
                                        if isinstance(v, list):
                                            st.markdown(f"**{k}**: {', '.join(str(i) for i in v)}")
                                        else:
                                            st.markdown(f"**{k}**: {v}")
                                else:
                                    st.markdown(str(layer_data))

                    # 记忆查看
                    mem_resp = httpx.get(f"{API_BASE}/agents/{detail_agent_id}/memories", timeout=10)
                    if mem_resp.status_code == 200:
                        mem_data = mem_resp.json()
                        episodic = mem_data.get("episodic", [])
                        semantic = mem_data.get("semantic", [])
                        if episodic or semantic:
                            with st.expander(f"🧠 记忆 (情景:{len(episodic)} 语义:{len(semantic)})"):
                                if semantic:
                                    st.markdown("**语义记忆**")
                                    for s in semantic:
                                        st.markdown(f"- {s['content']}")
                                if episodic:
                                    st.markdown("**情景记忆**")
                                    for e in episodic[:10]:
                                        st.markdown(f"- [{e['weight']:.2f}] {e['content']}")

                    # 社会关系查看
                    rel_resp = httpx.get(f"{API_BASE}/agents/{detail_agent_id}/relations", timeout=10)
                    if rel_resp.status_code == 200:
                        rel_data = rel_resp.json()
                        relations = rel_data.get("relations", [])
                        if relations:
                            with st.expander(f"🔗 社会关系 ({len(relations)}条)"):
                                type_icons = {"follow": "👉", "friend": "🤝", "oppose": "⚔", "mentor": "🎓", "same_org": "🏢"}
                                for r in relations:
                                    icon = type_icons.get(r["type"], "🔗")
                                    st.markdown(f"{icon} **{r['type']}** → {r['other_agent_id'][:12]}... (权重: {r['weight']:.2f})")
                else:
                    st.error(f"Agent不存在: {resp.text}")
            except Exception as e:
                st.error(f"连接失败: {e}")

    # 社会关系网络生成
    st.divider()
    st.markdown("**社会关系网络**")

    col_net, col_net_info = st.columns([1, 1])
    with col_net:
        net_k = st.slider("邻居数(k)", 2, 10, 4, key="net_k")
        net_beta = st.slider("重连概率(beta)", 0.0, 1.0, 0.3, step=0.1, key="net_beta")

        if st.button("🕸 生成关系网络", type="primary", key="gen_network_btn"):
            with st.spinner("正在生成社会关系网络..."):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/agents/network/generate",
                        json={"k": net_k, "beta": net_beta, "oppose_ratio": 0.1, "persist": True},
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success(f"网络生成完成: {data.get('total_relations', 0)} 条关系, {data.get('agent_count', 0)} 个Agent")
                        type_dist = data.get("type_distribution", {})
                        type_names = {"follow": "关注", "friend": "好友", "oppose": "对立", "mentor": "师徒", "same_org": "同组织"}
                        for t, c in type_dist.items():
                            st.markdown(f"- {type_names.get(t, t)}: {c} 条")
                    else:
                        st.error(f"生成失败: {resp.text}")
                except Exception as e:
                    st.error(f"连接失败: {e}")

    with col_net_info:
        st.info("社会关系网络基于Watts-Strogatz小世界模型生成，包含5种关系类型：关注、好友、对立、师徒、同组织。需要先有3个以上的活跃Agent。")
