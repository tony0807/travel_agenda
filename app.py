import streamlit as st
import json
import streamlit.components.v1 as components
from openai import OpenAI
import threading
import time
import random

# --- 页面配置 ---
st.set_page_config(
    page_title="Wanderlust AI · 智能旅行规划",
    layout="wide",
    page_icon="✈️",
    initial_sidebar_state="collapsed"
)

# 修复 iframe 滚动导致 sticky-topnav 无法吸顶的问题
st.markdown("""
<style>
/* 强制 iframe 不被撑开，使其能产生内部滚动条，激活内部 position: sticky */
iframe {
    height: 85vh !important;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
/* 隐藏主页多余内边距，使视图更沉浸 */
.block-container {
    padding-top: 2rem;
    padding-bottom: 5rem;
}
</style>
""", unsafe_allow_html=True)


# --- API 配置 ---
api_key = "sk-060b0e0759944181920f42d90aa3012a"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
model_name = "qwen3.5-27b"



# --- 核心逻辑：HTML 生成器 ---
def generate_html_template(json_data):
    try:
        data = json_data
        if isinstance(data, str):
            data = json.loads(data)
    except:
        return "<h3>JSON 解析失败，请重试</h3>"

    trip_title = data.get("trip_title", "MY JOURNEY")
    trip_subtitle = data.get("trip_subtitle", "Travel Itinerary")
    overview = data.get("overview", "")
    highlights = data.get("highlights", [])
    days_data = data.get("days", [])

    # 封面图：用 AI 返回的 cover_search 关键词 + 标题哈希种子，确保同一行程始终用同一张图
    cover_search = data.get("cover_search", trip_title).replace(" ", "+")
    # 放弃随机性极强但现在已被废弃且疯狂缓存的 Unsplash Source API
    # 改用更专业的免费图库：如果可能的话，后续推荐使用 Pixabay API 或 Pexels，这里为了前端纯动态拉取，使用带关键字的直接图片地址代理
    cover_url = f"https://wsrv.nl/?url=https://images.unsplash.com/photo-1488646953014-85cb44e25828&w=1080&h=1600&fit=cover" # Fallback placeholder


    # 生成日期快捷跳转按钮 HTML
    nav_buttons_html = ""
    for i, day in enumerate(days_data):
        date_label = day.get("date", f"Day {i+1}")
        city_label = day.get("city", "")
        nav_buttons_html += f"""<a onclick="document.getElementById('day-{i}').scrollIntoView({{behavior:'smooth', block:'start'}}); return false;" class="nav-pill" href="javascript:void(0)">{date_label}<span class="nav-city">{city_label}</span></a>"""

    # 亮点 HTML
    highlights_html = ""
    if highlights:
        highlights_html = '<div class="highlights-grid">'
        highlight_icons = ["🏛️", "🍜", "🌸", "🎭", "🛕", "🌊", "🏔️", "🎉", "🎨", "🚂"]
        for idx, h in enumerate(highlights):
            icon = highlight_icons[idx % len(highlight_icons)]
            highlights_html += f'<div class="highlight-chip"><span class="highlight-icon">{icon}</span><span contenteditable="true">{h}</span></div>'
        highlights_html += '</div>'

    # 生成 HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <link href="https://fonts.googleapis.com/css2?family=Italiana&family=Cinzel:wght@700&family=Noto+Serif+SC:wght@500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            :root {{
                --bg-color: #f0ebe3;
                --card-bg: #fdfbf7;
                --primary-dark: #2c2418;
                --accent-color: #b8860b;
                --accent-light: #daa520;
                --text-muted: #7a6e5f;
                --border-soft: rgba(74, 59, 42, 0.12);
            }}
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; font-family: 'Noto Serif SC', serif; background-color: var(--bg-color); color: var(--primary-dark); overflow-x: hidden; }}
            
            /* ===== 海报区域 ===== */
            .header-container {{ position: relative; width: 100%; height: 50vh; min-height: 350px; overflow: hidden; background: #1a1a1a; }}
            .header-poster {{ width: 100%; height: 100%; object-fit: cover; position: absolute; z-index: 1; opacity: 0; transition: opacity 1s ease; }}
            .header-poster.loaded {{ opacity: 1; }}
            .poster-overlay {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(to bottom, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0.65) 80%, rgba(0,0,0,0.9) 100%); z-index: 2; }}
            .header-title-box {{ position: absolute; bottom: 50px; width: 100%; text-align: center; color: #fff; z-index: 5; text-shadow: 0 3px 15px rgba(0,0,0,0.7); }}
            .main-title {{ font-family: 'Italiana', serif; font-size: 48px; margin: 0; text-transform: uppercase; letter-spacing: 6px; animation: fadeUp 1.2s ease; }}
            .sub-title {{ font-family: 'Cinzel', serif; font-size: 14px; letter-spacing: 4px; border-top: 1px solid rgba(255,255,255,0.5); display: inline-block; padding-top: 12px; margin-top: 14px; opacity: 0.9; }}
            @keyframes fadeUp {{ from {{ opacity: 0; transform: translateY(30px); }} to {{ opacity: 1; transform: translateY(0); }} }}
            
            /* ===== 顶部固定导航栏 ===== */
            .sticky-topnav {{
                position: sticky; top: 0; z-index: 200;
                background: rgba(240,235,227,0.96);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                border-bottom: 1px solid var(--border-soft);
                padding: 10px 16px;
                display: flex; gap: 8px; align-items: center; justify-content: center;
                overflow-x: auto; white-space: nowrap;
                -webkit-overflow-scrolling: touch;
                scrollbar-width: none;
            }}
            .sticky-topnav::-webkit-scrollbar {{ display: none; }}
            .nav-pill {{
                display: inline-flex; flex-direction: column; align-items: center; flex-shrink: 0;
                padding: 6px 14px; border-radius: 20px;
                background: var(--card-bg); border: 1.5px solid var(--border-soft);
                color: var(--primary-dark); text-decoration: none; cursor: pointer;
                font-family: 'Cinzel', serif; font-size: 12px; font-weight: 700;
                transition: all 0.2s ease; box-shadow: 0 1px 4px rgba(0,0,0,0.05);
                white-space: nowrap;
            }}
            .nav-pill:hover, .nav-pill.active {{
                background: var(--accent-color); color: #fff;
                border-color: var(--accent-color); box-shadow: 0 3px 10px rgba(184,134,11,0.3);
            }}
            .nav-pill .nav-city {{ font-family: 'Noto Serif SC', serif; font-size: 9px; opacity: 0.7; margin-top: 2px; }}
            .nav-pill:hover .nav-city, .nav-pill.active .nav-city {{ opacity: 1; }}
            .nav-divider {{ width: 1px; height: 24px; background: var(--border-soft); flex-shrink: 0; margin: 0 2px; }}

            .overview-label {{ font-family: 'Cinzel', serif; font-size: 11px; letter-spacing: 3px; text-transform: uppercase; color: var(--accent-color); margin-bottom: 8px; }}
            .overview-text {{ font-size: 15px; line-height: 1.9; color: var(--text-muted); text-align: justify; margin-bottom: 20px; }}
            
            .highlights-grid {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 10px; }}
            .highlight-chip {{
                display: inline-flex; align-items: center; gap: 6px;
                background: var(--card-bg); border: 1px solid var(--border-soft);
                padding: 8px 14px; border-radius: 20px; font-size: 13px;
                transition: all 0.2s ease;
            }}
            .highlight-chip:hover {{ background: #fff8e7; border-color: var(--accent-light); }}
            .highlight-icon {{ font-size: 16px; }}
            
            .section-divider {{ height: 1px; background: linear-gradient(to right, transparent, var(--border-soft), var(--accent-color), var(--border-soft), transparent); margin: 24px 0; }}
            
            /* ===== 弹窗模态框 ===== */
            .modal-overlay {{
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
                z-index: 1000; display: none; align-items: center; justify-content: center;
                opacity: 0; transition: opacity 0.3s ease;
            }}
            .modal-overlay.show {{ display: flex; opacity: 1; }}
            .overview-modal {{
                width: 90%; max-width: 600px; max-height: 80vh; overflow-y: auto;
                background: var(--bg-color); border-radius: 20px; padding: 30px 24px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.2); position: relative;
                transform: translateY(20px); transition: transform 0.3s ease;
            }}
            .modal-overlay.show .overview-modal {{ transform: translateY(0); }}
            .close-modal-btn {{
                position: absolute; top: 16px; right: 16px;
                background: rgba(0,0,0,0.05); border: none; font-size: 18px; color: var(--text-muted);
                width: 32px; height: 32px; border-radius: 50%; cursor: pointer;
                display: flex; align-items: center; justify-content: center; transition: all 0.2s;
            }}
            .close-modal-btn:hover {{ background: #ff4d4f; color: #fff; }}

            /* ===== 时间线 ===== */
            .timeline-container {{ max-width: 640px; margin: 0 auto; padding: 0 16px 60px; }}
            .day-header {{
                position: sticky; top: 53px; z-index: 100;
                background: linear-gradient(to bottom, var(--bg-color) 80%, rgba(240,235,227,0));
                padding: 18px 0 12px; display: flex; justify-content: space-between; align-items: baseline;
                margin-bottom: 20px; border-bottom: 2px solid var(--primary-dark);
            }}
            .day-num {{ font-family: 'Cinzel', serif; font-size: 24px; font-weight: 800; letter-spacing: 1px; }}
            .day-city {{ font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; letter-spacing: 2px; color: var(--accent-color); text-transform: uppercase; }}
            
            .timeline-item {{ position: relative; padding-left: 20px; margin-bottom: 35px; border-left: 2px dashed rgba(74, 59, 42, 0.2); margin-left: 60px; }}
            .timeline-item::before {{ content: ''; position: absolute; left: -8px; top: 6px; width: 14px; height: 14px; background: var(--accent-light); border-radius: 50%; border: 3px solid var(--bg-color); z-index: 2; }}
            .time-label {{ position: absolute; left: -65px; top: 3px; width: 45px; text-align: right; font-family: 'Inter', sans-serif; font-size: 13px; font-weight: 700; color: var(--primary-dark); }}
            
            .card {{ background: var(--card-bg); border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); overflow: hidden; margin-top: 8px; transition: transform 0.2s ease, box-shadow 0.2s ease; position: relative; }}
            .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.1); }}
            .location-name {{ font-size: 17px; font-weight: bold; margin-bottom: 6px; display: inline-block; padding-right: 30px; }}
            
            /* 删除按钮 (大卡片层级) - 更加显眼 */
            .delete-btn {{
                position: absolute; top: 12px; right: 12px; z-index: 600;
                padding: 6px 12px; border-radius: 12px;
                background: rgba(255, 235, 235, 0.9); border: 1px solid #ffccc7;
                color: #f5222d; font-size: 12px; font-weight: 600;
                display: flex; align-items: center; justify-content: center; gap: 4px;
                cursor: pointer; transition: all 0.2s; text-decoration: none;
                box-shadow: 0 2px 6px rgba(245,34,45,0.15);
            }}
            .delete-btn:hover {{ background: #ff4d4f; color: #fff; border-color: #ff4d4f; box-shadow: 0 4px 12px rgba(245,34,45,0.3); }}
            
            /* 删除局部媒体 (地图/图片) */
            .remove-media-btn {{
                position: absolute; top: 8px; right: 8px; z-index: 600;
                width: 20px; height: 20px; border-radius: 50%;
                background: rgba(0,0,0,0.5); border: none;
                color: #fff; font-size: 10px; font-weight: bold;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer; transition: background 0.2s;
            }}
            .remove-media-btn:hover {{ background: #ff4d4f; }}
            
            /* 地图 */
            .map-section {{ height: 160px; width: 100%; position: relative; z-index: 1; }}
            .nav-to-btn-group {{ position: absolute; bottom: 10px; right: 10px; z-index: 500; display: flex; gap: 6px; }}
            .nav-btn {{
                background: rgba(255,255,255,0.9); color: #333; border: 1px solid #ddd;
                padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 600;
                cursor: pointer; text-decoration: none; box-shadow: 0 2px 6px rgba(0,0,0,0.15); transition: background 0.2s;
            }}
            .nav-btn:hover {{ background: #fff; }}
            .nav-btn.amap {{ color: #2577e3; border-color: #2577e3; }}
            
            /* 景点照片（留足间距） */
            .photo-wrapper {{ height: 220px; width: 100%; position: relative; background: linear-gradient(135deg, #e8e0d4, #d4cbbe); overflow: hidden; margin-top: 32px; border-radius: 8px 8px 0 0; border-top: 2px solid var(--border-soft); }}
            .photo-wrapper img {{ width: 100%; height: 100%; object-fit: cover; opacity: 0; transition: opacity 0.6s ease; }}
            .photo-wrapper img.loaded {{ opacity: 1; }}
            .photo-placeholder {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 14px; color: var(--text-muted); }}
            
            /* 备注设计 */
            .remark-box {{ padding: 16px; background: #fff; border-top: 1px solid var(--border-soft); }}
            .remark-label {{ font-family: 'Cinzel', serif; font-size: 10px; letter-spacing: 2px; color: var(--accent-color); margin-bottom: 6px; display: flex; align-items: center; gap: 4px; }}
            .remark-text {{ font-size: 14px; line-height: 1.75; color: #555; }}
            
            /* 可编辑样式 */
            [contenteditable="true"]:hover {{ background: rgba(255, 235, 59, 0.15); cursor: text; outline: 1px dashed #ccc; border-radius: 4px; }}
            [contenteditable="true"]:focus {{ background: rgba(255, 235, 59, 0.25); outline: 2px solid var(--accent-light); border-radius: 4px; }}
            
            /* 打印按钮 */
            .print-btn {{
                position: fixed; bottom: 24px; right: 24px;
                background: linear-gradient(135deg, var(--accent-color), var(--accent-light));
                color: white; border: none; padding: 14px 24px; border-radius: 30px;
                box-shadow: 0 6px 20px rgba(184,134,11,0.4); z-index: 1000; cursor: pointer;
                font-weight: bold; font-size: 14px; letter-spacing: 0.5px;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .print-btn:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(184,134,11,0.5); }}
            
            /* 回到顶部 */
            .top-btn {{
                position: fixed; bottom: 24px; left: 24px;
                background: var(--primary-dark); color: #fff; border: none;
                padding: 12px 16px; border-radius: 50%; font-size: 18px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 1000; cursor: pointer;
                transition: transform 0.2s;
            }}
            .top-btn:hover {{ transform: translateY(-3px); }}
            
            @media print {{
                .print-btn, .top-btn, .nav-to-btn, .sticky-topnav, .delete-btn, .remove-media-btn {{ display: none; }}
                .header-container {{ height: 45vh; }}
                body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
            }}
            
            /* ===== 手机端自适应 (max-width: 600px) ===== */
            @media (max-width: 600px) {{
                /* 海报标题变小 */
                .main-title {{ font-size: 28px; letter-spacing: 3px; }}
                .sub-title {{ font-size: 11px; letter-spacing: 2px; }}
                .header-container {{ height: 40vh; min-height: 250px; }}
                .header-title-box {{ bottom: 30px; }}

                /* 总览區内边距变小 */
                .overview-section {{ padding: 20px 14px 10px; }}
                .overview-text {{ font-size: 14px; }}
                .highlight-chip {{ padding: 6px 10px; font-size: 12px; }}
                .nav-pill {{ padding: 7px 12px; font-size: 12px; }}

                /* 时间线：小屏上保留时间，使其嵌入行内并可编辑，减小 margin */
                .timeline-container {{ padding: 0 12px 60px; }}
                .timeline-item {{ margin-left: 0; padding-left: 18px; }}
                .time-label {{ position: static; display: inline-block; padding-right: 6px; font-size: 14px; text-align: left; width: auto; color: var(--accent-light); }}
                .timeline-item::before {{ left: -7px; width: 12px; height: 12px; }}
                .location-name {{ font-size: 15px; display: inline; }}
                .day-num {{ font-size: 20px; }}

                /* 地图和图片 */
                .map-section {{ height: 140px; }}
                .photo-wrapper {{ height: 180px; }}
                .remark-box {{ font-size: 13px; padding: 12px; }}

                /* 导航按钮加大点击区域 */
                .nav-btn {{ padding: 8px 14px; font-size: 12px; }}
                
                /* 打印和回顶按钮移动下方避免遮住内容 */
                .print-btn {{ bottom: 16px; right: 12px; padding: 10px 16px; font-size: 13px; }}
                .top-btn {{ bottom: 16px; left: 12px; padding: 10px 13px; font-size: 16px; }}
            }}

            html {{ scroll-behavior: smooth; }}
        </style>
    </head>
    <body>
        <!-- 海报区 -->
        <div class="header-container">
            <!-- 动态加载封面：摒弃 Unsplash, 这里用 JS 异步通过 Wiki 抓取 -->
            <img id="main-cover-img" src="" class="header-poster" onload="this.classList.add('loaded')" onerror="this.src='https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1080&h=1600&fit=crop'; this.classList.add('loaded');">
            <div class="poster-overlay"></div>
            <div class="header-title-box">
                <h1 class="main-title" contenteditable="true">{trip_title}</h1>
                <p class="sub-title" contenteditable="true">{trip_subtitle}</p>
            </div>
        </div>

        <!-- 顶部固定快捷导航栏 -->
        <div class="sticky-topnav">
            <a class="nav-pill" onclick="openModal('section-overview'); return false;" href="javascript:void(0)">总览<span class="nav-city">Overview</span></a>
            <a class="nav-pill" onclick="openModal('section-highlights'); return false;" href="javascript:void(0)">亮点<span class="nav-city">Highlights</span></a>
            <div class="nav-divider"></div>
            {nav_buttons_html}
        </div>

        <!-- 弹窗模态框：总览 + 亮点 -->
        <div class="modal-overlay" id="info-modal" onclick="if(event.target===this) closeModal();">
            <div class="overview-modal">
                <button class="close-modal-btn" onclick="closeModal()">✖</button>
                <div id="section-overview">
                    <p class="overview-label">✦ Trip Overview</p>
                    <p class="overview-text" contenteditable="true">{overview}</p>
                </div>
                <div class="section-divider"></div>
                <div id="section-highlights">
                    <p class="overview-label">✦ Highlights</p>
                    {highlights_html}
                </div>
            </div>
        </div>
        
        <!-- 时间线 -->
        <div class="timeline-container">
            <button class="print-btn" onclick="window.print()">🖨️ 保存行程 (PDF)</button>
            <button class="top-btn" onclick="window.scrollTo({{top:0, behavior:'smooth'}})">↑</button>
    """
    
    js_map_data = []
    map_counter = 0

    for day_idx, day in enumerate(days_data):
        date = day.get("date", "Day")
        city = day.get("city", "").upper()
        html += f"""<div id="day-{day_idx}" class="day-header"><span class="day-num" contenteditable="true">{date}</span><span class="day-city" contenteditable="true">{city}</span></div>"""
        
        for act in day.get("activities", []):
            map_counter += 1
            map_id = f"map-{map_counter}"
            
            time = act.get("time", "")
            name = act.get("name", "")
            desc = act.get("desc", "")
            lat = act.get("lat", 0)
            lng = act.get("lng", 0)
            # Wikipedia 图片 ID（程序详见 JS 部分动态加载）
            wiki_query = act.get("img_keyword", name)
            photo_id = f"photo-{map_id}"
            fallback_url = "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=600&h=400&fit=crop"
            
            # 导航链接
            nav_google = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            nav_amap = f"https://uri.amap.com/navigation?to={lng},{lat},{name}"
            
            js_map_data.append({"id": map_id, "lat": lat, "lng": lng, "name": name, "wiki_query": wiki_query, "photo_id": photo_id})
            
            html += f"""
            <div class="timeline-item">
                <span class="time-label" contenteditable="true">{time}</span>
                <span class="location-name" contenteditable="true">{name}</span>
                <div class="card">
                    <button class="delete-btn" title="删除此行程" onclick="this.closest('.timeline-item').remove()">🗑️ 删除</button>
                    <div class="map-section" id="{map_id}">
                        <button class="remove-media-btn" title="删除地图" onclick="this.parentElement.remove()">✖</button>
                        <div class="nav-to-btn-group">
                            <a href="{nav_amap}" target="_blank" class="nav-btn amap">高德</a>
                            <a href="{nav_google}" target="_blank" class="nav-btn">Google</a>
                        </div>
                    </div>
                    <div class="photo-wrapper">
                        <button class="remove-media-btn" title="删除照片" onclick="this.parentElement.remove()">✖</button>
                        <span class="photo-placeholder">📷 加载中...</span>
                        <img id="{photo_id}" src="" onload="this.classList.add('loaded'); this.previousElementSibling.style.display='none';" onerror="this.src='{fallback_url}'; this.classList.add('loaded'); this.previousElementSibling.style.display='none';">
                    </div>
                    <div class="remark-box">
                        <div class="remark-label">💡 TIPS</div>
                        <div class="remark-text" contenteditable="true">{desc}</div>
                    </div>
                </div>
            </div>
            """

    # JS 注入 — 地图 + 附近 POI
    js_data = json.dumps(js_map_data, ensure_ascii=False)
    html += f"""
        </div>
        <script>
            const mapPoints = {js_data};
            const coverSearchQuery = "{cover_search}";
            
            document.addEventListener("DOMContentLoaded", function () {{
                
                // --- 1. 动态加载首页大图 (使用 Wikipedia API 或备用 API) ---
                var coverImgEl = document.getElementById('main-cover-img');
                var genericFallback = 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=1080&h=1600&fit=crop';
                fetch('https://en.wikipedia.org/w/api.php?action=query&titles=' + encodeURIComponent(coverSearchQuery.split(' ')[0]) + '&prop=pageimages&format=json&pithumbsize=1600&origin=*')
                    .then(r => r.json())
                    .then(d => {{
                        var pages = d.query.pages;
                        var page = pages[Object.keys(pages)[0]];
                        if (page && page.thumbnail) {{
                            coverImgEl.src = page.thumbnail.source;
                        }} else {{
                            // 如果 Wiki 没找到，使用基于关键字生成随机数确保固定的强力占位服务 (避免Unsplash Source 的完全废弃缓存)
                            coverImgEl.src = 'https://picsum.photos/seed/' + encodeURIComponent(coverSearchQuery) + '/1080/1600';
                        }}
                    }}).catch(() => {{ coverImgEl.src = genericFallback; }});


                // --- 2. 加载行程地图与景点图片 ---
                mapPoints.forEach(pt => {{
                        var cartoLayer = L.tileLayer('https://{{s}}.basemaps.cartocdn.com/rastertiles/voyager/{{z}}/{{x}}/{{y}}{{r}}.png', {{ maxZoom: 19 }});
                        // 高德地图 HTTPS 兼容版：使用 wprd 子域名，确保能够正常加载显示
                        var amapLayer = L.tileLayer('https://wprd01.is.autonavi.com/appmaptile?x={{x}}&y={{y}}&z={{z}}&lang=zh_cn&size=1&scl=1&style=7', {{ maxZoom: 19 }});

                        // 智能判断：如果经纬度落在中国大致范围内，则默认选中高德地图，否则默认国际地图
                        var isChina = (pt.lat > 18.0 && pt.lat < 53.5 && pt.lng > 73.0 && pt.lng < 135.0);
                        var defaultLayer = isChina ? amapLayer : cartoLayer;

                        var map = L.map(pt.id, {{
                            zoomControl: false, scrollWheelZoom: false, attributionControl: false,
                            layers: [defaultLayer]
                        }}).setView([pt.lat, pt.lng], 12);
                        
                        // 图层控制菜单
                        if (isChina) {{
                            L.control.layers({{"高德地图(默认)": amapLayer, "国际地图": cartoLayer}}, null, {{position: 'topleft'}}).addTo(map);
                        }} else {{
                            L.control.layers({{"国际地图(默认)": cartoLayer, "高德地图": amapLayer}}, null, {{position: 'topleft'}}).addTo(map);
                        }}
                        
                        L.control.scale({{ position: 'bottomleft', metric: true, imperial: false }}).addTo(map);

                        // Wikipedia API 动态加载景点真实图片
                        (function(photoId, wikiQuery) {{
                            var imgEl = document.getElementById(photoId);
                            var fallback = 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=600&h=400&fit=crop';
                            fetch('https://en.wikipedia.org/w/api.php?action=query&titles=' + encodeURIComponent(wikiQuery) + '&prop=pageimages&format=json&pithumbsize=800&origin=*')
                                .then(function(r) {{ return r.json(); }})
                                .then(function(d) {{
                                    var pages = d.query.pages;
                                    var page = pages[Object.keys(pages)[0]];
                                    if (page && page.thumbnail) {{
                                        imgEl.src = page.thumbnail.source;
                                    }} else {{
                                        // fallback: Unsplash 搜索
                                        imgEl.src = 'https://source.unsplash.com/600x400/?' + encodeURIComponent(wikiQuery) + '&sig=' + Math.abs(wikiQuery.split('').reduce(function(a,c){{return a+c.charCodeAt(0)}}, 0));
                                    }}
                                }}).catch(function() {{ imgEl.src = fallback; }});
                        }})(pt.photo_id, pt.wiki_query);

                        // 主标记 — 红色
                        var mainIcon = L.divIcon({{
                            className: 'custom-marker',
                            html: '<div style="background:#e74c3c;width:14px;height:14px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>',
                            iconSize: [14, 14],
                            iconAnchor: [7, 7]
                        }});
                        L.marker([pt.lat, pt.lng], {{icon: mainIcon}}).addTo(map).bindPopup('<b>' + pt.name + '</b>');

                        // 使用 Nominatim 查询周边 POI
                        fetch('https://nominatim.openstreetmap.org/search?format=json&limit=6&viewbox=' + 
                            (pt.lng - 0.015) + ',' + (pt.lat + 0.015) + ',' + (pt.lng + 0.015) + ',' + (pt.lat - 0.015) + 
                            '&bounded=1&q=tourism+OR+restaurant+OR+museum+OR+temple+OR+park+OR+hotel')
                        .then(res => res.json())
                        .then(places => {{
                            places.forEach(p => {{
                                if(Math.abs(p.lat - pt.lat) > 0.0005 || Math.abs(p.lon - pt.lng) > 0.0005) {{
                                    var poiIcon = L.divIcon({{
                                        className: 'poi-marker',
                                        html: '<div style="background:#3498db;width:8px;height:8px;border-radius:50%;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>',
                                        iconSize: [8, 8],
                                        iconAnchor: [4, 4]
                                    }});
                                    L.marker([parseFloat(p.lat), parseFloat(p.lon)], {{icon: poiIcon}}).addTo(map)
                                        .bindPopup('<small>' + p.display_name.split(',')[0] + '</small>');
                                }}
                            }});
                        }}).catch(()=>{{}});
                    }}
                }});
            // 控制弹窗
            function openModal(targetId) {{
                var modal = document.getElementById('info-modal');
                modal.classList.add('show');
                setTimeout(function() {{
                    var target = document.getElementById(targetId);
                    if(target) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                }}, 100);
            }}
            function closeModal() {{
                document.getElementById('info-modal').classList.remove('show');
            }}

            // 监听键盘 ESC 关闭弹窗
            document.addEventListener('keydown', function(event) {{
                if (event.key === "Escape") {{
                    closeModal();
                }}
            }});
        </script>
    </body>
    </html>
    """
    return html

# --- 主界面 ---
st.title("✈️ 你的旅程，我来安排")
st.markdown("*读万卷书，行万里路 · 愿每一段旅途，皆成值得珍藏的诗章*")

# 优化底部 chat_input 样式，使其更宽广大气
st.markdown("""
<style>
/* chat 输入框容器 */
[data-testid="stChatInput"] {
    padding-bottom: 20px;
}
/* 撑高文本域：增加上下左右四周边距，让文字更有呼吸感 */
[data-testid="stChatInput"] textarea {
    min-height: 72px !important;
    max-height: 110px !important;
    line-height: 1.7 !important;
    padding: 20px 24px !important; 
    font-size: 16px !important;
    overflow-y: auto !important;
    border-radius: 12px !important;
}
/* 发送按钮稍微往下一点对齐居中 */
[data-testid="stChatInput"] button {
    height: auto !important;
    padding-top: 10px !important;
}
/* 确保占位文字不被截断，且带有呼吸感 */
[data-testid="stChatInput"] textarea::placeholder {
    line-height: 1.8;
    white-space: pre-wrap;
    opacity: 0.6;
}
</style>
""", unsafe_allow_html=True)

# 聊天输入框 - 官方原生吸底输入框
prompt_text = st.chat_input("你想去哪里？玩几天？什么风格？例如：我想去日本京都玩3天，喜欢古建筑和美食")

if prompt_text:
    # 旅行趣知识小贴士列表
    TRAVEL_TIPS = [
        ("✈️", "出发前请确认护照有效期至少还剩 6 个月，部分国家还需提前办理签证哦"),
        ("🌍", "世界上有超过 195 个国家，若每天去一个新地方，也要游历半年以上"),
        ("🍜", "当地街头小吃往往比高档餐厅更能代表一座城市的灵魂味道"),
        ("🗺️", "意大利拥有超过 58 处 UNESCO 世界遗产，居全球第一"),
        ("🚂", "坐火车旅行往往能看到飞机上看不到的风景，感受距离真实的流动"),
        ("🌸", "日本每年有超过 80 种樱花，选对时间地点才能赏到最美的はな"),
        ("🏖️", "澳大利亚大堡礁的巨型珊瑚礁，实际上是卧米级的巨大碳酸钙板！"),
        ("🎒", "长途旅行的最好朋友是一只轻便的行李箱——不知道带什么就少带点"),
        ("🌊", "太平洋算不上真正的'太平'，麦哲伦诗人认为它该叫'疯狂之洋'"),
        ("🏔️", "珠峰海拔处大气量约为海平面和山脚平地的三分之一，模糊天际线是最检验耐力的测试"),
        ("🎨", "法国卢浮宫目前内刻有超过 380,000 件藏品，展出来要排队几百年！"),
        ("🌮", "墨西哥委内瑞拉事实上有超过 40 种不同的玉米亚水，每一种都值得单独一次旅行"),
        ("🎥", "布宜诺斯艾利斯荆斯火车站是许多电影的拍摄地，你可能不经意间就走过了某个经典镜头"),
        ("🍿", "寻找景点付费停车位的小技巧：选择附近超市停车场，常常免费时达两小时"),
    ]

    result_store = {}

    def call_api():
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            system_prompt = """
你是一个旅行规划 API。请严格只输出 JSON 数据，不要包含 ```json 或其他 markdown 标记。
输出结构：
{
  "trip_title": "主标题(英文，简短有格调)",
  "trip_subtitle": "副标题(英文)",
  "overview": "行程总览，用2-3句话介绍这趟旅行的整体安排和亮点(中文)",
  "highlights": ["亮点1", "亮点2", "亮点3", "亮点4", "亮点5"],
  "days": [
    {
      "date": "Day 1",
      "city": "城市名",
      "activities": [
        { "time": "10:00", "name": "景点名", "desc": "丰富生动的介绍和游玩建议，不少于50字(中文)", "lat": 0.0, "lng": 0.0, "img_keyword": "必须使用景点全称英文+所在城市名，如 Eiffel Tower Paris" }
      ]
    }
  ]
}
注意：
1. overview 必须用中文，生动简洁
2. cover_search 必须是英文，精准描述目的地风景，如 Kyoto Japan autumn maple red leaves
3. highlights 至少5条，每条10字以内，中文
4. img_keyword 必须精准，景点英文全称+城市名，用于Wikipedia搜图
5. desc 要生动俏皮，可以加网络用语，不要死板，不少于60字
6. lat/lng 坐标必须准确
"""
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            result_store["data"] = json.loads(content)
        except Exception as e:
            result_store["error"] = str(e)

    # 启动后台线程调用 API
    api_thread = threading.Thread(target=call_api)
    api_thread.start()

    # 诗意加载提示语列表
    POETIC_STATUSES = [
        "晓看天色暮看云，正为您将沿途星辰与风物，细细描摹……",
        "落霞与孤鹜齐飞，秋水共长天一色，正在为您铺展绝美画卷……",
        "长风破浪会有时，直挂云帆济沧海，正在为您规划破浪之旅……",
        "星垂平野阔，月涌大江流，正在为您寻觅天地间最辽阔的风景……",
        "春风得意马蹄疾，一日看尽长安花，正在为您编排最畅快的行程……",
        "白日放歌须纵酒，青春作伴好还乡，正在为您酿造旅途的醇厚回味……",
        "大漠孤烟直，长河落日圆，正在为您捕捉天地间最震撼的瞬间……",
        "海内存知己，天涯若比邻，正在为您丈量世界的每一个角落……"
    ]

    # 主线程展示动态旅行趣知识提示与诗意状态
    status_box = st.empty()
    tip_box = st.empty()
    
    # 每次生成随机抽取一句诗意状态，保持在整个 generation 过程中不变
    current_status = random.choice(POETIC_STATUSES)
    shuffled_tips = random.sample(TRAVEL_TIPS, len(TRAVEL_TIPS))
    tip_index = 0
    
    while api_thread.is_alive():
        emoji, tip = shuffled_tips[tip_index % len(shuffled_tips)]
        status_box.markdown(f"#### ⏳ {current_status}")
        tip_box.info(f"**{emoji} 旅行小知识**\n\n{tip}")
        tip_index += 1
        time.sleep(3)

    api_thread.join()
    status_box.empty()
    tip_box.empty()

    if "error" in result_store:
        st.error(f"发生错误: {result_store['error']}")
        st.info("建议重试一次。")
    else:
        json_data = result_store["data"]
        html_code = generate_html_template(json_data)
        st.success("✨ 生成成功！您可以在下方直接编辑文字，点击右下角按钮保存为 PDF。")
        total_days = len(json_data.get("days", []))
        total_acts = sum(len(d.get("activities", [])) for d in json_data.get("days", []))
        # 只要给一个基础 height 让内部能生出滚动条（CSS已经用了 85vh !important 进行覆盖） 
        components.html(html_code, height=800, scrolling=True)