import html as html_lib
import os
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-5.5"
MAX_TOKENS = 300
HISTORY_WINDOW = 10
MAX_API_ERRORS = 3


def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except Exception:
            pass
    return OpenAI(api_key=api_key)


# ── session_state 초기화 ────────────────────────────────────────────────────

def init_state():
    defaults = {
        "screen": "settings",
        "topic": "",
        "agent_a": {"name": "", "persona": ""},
        "agent_b": {"name": "", "persona": ""},
        "messages": [],
        "loading": False,
        "space_pressed": False,
        "api_errors": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── OpenAI API ──────────────────────────────────────────────────────────────

def build_system_prompt(speaker: str) -> str:
    me = st.session_state.agent_a if speaker == "AI_A" else st.session_state.agent_b
    opponent = st.session_state.agent_b if speaker == "AI_A" else st.session_state.agent_a
    persona_summary = opponent["persona"][:50] + ("..." if len(opponent["persona"]) > 50 else "")
    return (
        f"당신은 {me['name']}입니다.\n"
        f"페르소나: {me['persona']}\n\n"
        f"대화 주제: {st.session_state.topic}\n"
        f"상대방: {opponent['name']} ({persona_summary})\n\n"
        "규칙:\n"
        "- 반드시 한 번에 3~5문장 이내로 간결하게 발언하세요\n"
        "- 상대방의 직전 발언에 반응하여 대화를 이어가세요\n"
        "- 주제에서 벗어나지 마세요"
    )


def build_openai_messages(speaker: str) -> list:
    history = st.session_state.messages[-HISTORY_WINDOW:]
    result = []
    for msg in history:
        role = "assistant" if msg["role"] == speaker else "user"
        result.append({"role": role, "content": f"{msg['name']}: {msg['content']}"})
    return result


def generate_response(speaker: str) -> str | None:
    if st.session_state.api_errors >= MAX_API_ERRORS:
        st.error(f"API 오류가 {MAX_API_ERRORS}회 연속 발생했습니다. "
                 "API 키와 네트워크 상태를 확인한 뒤 [처음부터 다시]를 눌러주세요.")
        return None
    try:
        client = get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": build_system_prompt(speaker)}]
                     + build_openai_messages(speaker),
            max_completion_tokens=MAX_TOKENS,
        )
        st.session_state.api_errors = 0
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.session_state.api_errors += 1
        left = MAX_API_ERRORS - st.session_state.api_errors
        msg = f"재시도 가능 횟수: {left}회" if left > 0 else "최대 오류 횟수에 도달했습니다."
        st.error(f"API 오류 ({st.session_state.api_errors}/{MAX_API_ERRORS}) — {msg}\n\n`{e}`")
        return None


def next_speaker() -> str:
    return "AI_A" if len(st.session_state.messages) % 2 == 0 else "AI_B"


# ── 설정 화면 ───────────────────────────────────────────────────────────────

def render_settings():
    st.title("🤖 AI 듀얼 대화")
    st.caption("두 AI 페르소나를 설정하고 대화를 시작하세요.")
    st.divider()

    topic = st.text_input(
        "대화 주제",
        value=st.session_state.topic,
        placeholder="예: 인공지능이 인간을 대체할 것인가",
    )

    st.markdown("#### AI 설정")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**AI A**")
        name_a = st.text_input("이름", value=st.session_state.agent_a["name"],
                               placeholder="예: 철학자", key="name_a")
        persona_a = st.text_area("페르소나", value=st.session_state.agent_a["persona"],
                                  placeholder="예: 소크라테스식 문답법으로 질문 중심 대화",
                                  height=140, key="persona_a")
    with col_b:
        st.markdown("**AI B**")
        name_b = st.text_input("이름", value=st.session_state.agent_b["name"],
                               placeholder="예: 과학자", key="name_b")
        persona_b = st.text_area("페르소나", value=st.session_state.agent_b["persona"],
                                  placeholder="예: 데이터와 근거 중심, 단호한 어조",
                                  height=140, key="persona_b")

    st.divider()

    if st.button("대화 시작 ▶", type="primary", use_container_width=True):
        errors = []
        if not topic.strip():
            errors.append("대화 주제를 입력해주세요.")
        if not name_a.strip() or not name_b.strip():
            errors.append("두 AI의 이름을 모두 입력해주세요.")
        if not persona_a.strip() or not persona_b.strip():
            errors.append("두 AI의 페르소나를 모두 입력해주세요.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            st.session_state.topic = topic.strip()
            st.session_state.agent_a = {"name": name_a.strip(), "persona": persona_a.strip()}
            st.session_state.agent_b = {"name": name_b.strip(), "persona": persona_b.strip()}
            st.session_state.messages = []
            st.session_state.loading = False
            st.session_state.space_pressed = False
            st.session_state.api_errors = 0
            st.session_state.screen = "chat"
            st.rerun()


# ── 대화 화면 ───────────────────────────────────────────────────────────────

def render_bubble(msg: dict, index: int):
    """AI A = 왼쪽 파란 말풍선 / AI B = 오른쪽 초록 말풍선"""
    turn = index // 2 + 1
    is_a = msg["role"] == "AI_A"
    label = html_lib.escape(f"{msg['name']} #{turn}")
    content = html_lib.escape(msg["content"]).replace("\n", "<br>")

    if is_a:
        st.markdown(f"""
        <div style="display:flex;justify-content:flex-start;margin:10px 0 16px 0;">
          <div style="background:#DBEAFE;border-radius:18px 18px 18px 4px;
                      padding:14px 18px;max-width:75%;color:#1E3A5F;
                      box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <div style="font-size:12px;font-weight:700;margin-bottom:8px;opacity:0.65;">{label}</div>
            <div style="line-height:1.65;font-size:15px;">{content}</div>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display:flex;justify-content:flex-end;margin:10px 0 16px 0;">
          <div style="background:#DCFCE7;border-radius:18px 18px 4px 18px;
                      padding:14px 18px;max-width:75%;color:#14532D;
                      box-shadow:0 1px 3px rgba(0,0,0,0.08);">
            <div style="font-size:12px;font-weight:700;margin-bottom:8px;opacity:0.65;text-align:right;">{label}</div>
            <div style="line-height:1.65;font-size:15px;">{content}</div>
          </div>
        </div>""", unsafe_allow_html=True)


def auto_scroll():
    components.html("""
    <script>
      setTimeout(function() {
        const selectors = [
          '[data-testid="stAppViewBlockContainer"]',
          '[data-testid="stAppViewContainer"]',
          'section.main',
        ];
        for (const sel of selectors) {
          const el = window.parent.document.querySelector(sel);
          if (el) { el.scrollTop = el.scrollHeight; break; }
        }
      }, 150);
    </script>
    """, height=0)


def spacebar_listener(disabled: bool = False):
    """스페이스바 입력을 감지하여 primary 버튼을 클릭.
    window.parent.__spaceListener 로 단일 리스너를 유지해 중복 등록을 방지."""
    disabled_js = "true" if disabled else "false"
    components.html(f"""
    <script>
    (function() {{
      // 이전 리스너 항상 정리
      if (window.parent.__spaceListener) {{
        window.parent.document.removeEventListener('keydown', window.parent.__spaceListener);
        window.parent.__spaceListener = null;
      }}
      if ({disabled_js}) return;

      window.parent.__spaceListener = function(e) {{
        if (e.code !== 'Space') return;
        const tag = (e.target || {{}}).tagName || '';
        if (['INPUT', 'TEXTAREA'].includes(tag)) return;
        e.preventDefault();
        // 한 번만 실행 후 자기 제거
        window.parent.document.removeEventListener('keydown', window.parent.__spaceListener);
        window.parent.__spaceListener = null;
        const btn = window.parent.document.querySelector('[data-testid="stBaseButton-primary"]');
        if (btn) btn.click();
      }};
      window.parent.document.addEventListener('keydown', window.parent.__spaceListener);
    }})();
    </script>
    """, height=0)


def do_generate(speaker: str, name: str):
    """발언 생성 실행 (버튼 클릭 / 스페이스바 양쪽에서 호출)"""
    st.session_state.loading = True
    with st.spinner(f"{name}의 발언을 생성하는 중..."):
        content = generate_response(speaker)
    st.session_state.loading = False
    if content:
        st.session_state.messages.append({"role": speaker, "name": name, "content": content})
    st.rerun()


def render_chat():
    a = st.session_state.agent_a
    b = st.session_state.agent_b

    st.title(f"💬 {a['name']} vs {b['name']}")
    st.caption(f"주제: {st.session_state.topic}")

    # AI A 첫 발언 자동 생성
    if not st.session_state.messages and not st.session_state.loading:
        st.session_state.loading = True
        with st.spinner(f"{a['name']}의 첫 발언을 생성하는 중..."):
            content = generate_response("AI_A")
        st.session_state.loading = False
        if content:
            st.session_state.messages.append({"role": "AI_A", "name": a["name"], "content": content})
            st.rerun()

    # 말풍선 렌더링
    for i, msg in enumerate(st.session_state.messages):
        render_bubble(msg, i)

    if st.session_state.messages:
        auto_scroll()

    st.divider()

    speaker = next_speaker()
    next_name = a["name"] if speaker == "AI_A" else b["name"]
    loading = st.session_state.loading

    spacebar_listener(disabled=loading)

    if not loading:
        if st.button(f"▶ {next_name} 발언 생성  ·  스페이스바를 누르세요", type="primary", use_container_width=True):
            do_generate(speaker, next_name)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⟳ 처음부터 다시", use_container_width=True):
            st.session_state.messages = []
            st.session_state.loading = False
            st.session_state.space_pressed = False
            st.session_state.api_errors = 0
            st.rerun()
    with col2:
        if st.button("🏠 홈", key="home_btn_bottom", use_container_width=True):
            st.session_state.screen = "settings"
            st.rerun()


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="AI 듀얼 대화", page_icon="🤖", layout="centered")
    init_state()

    if st.session_state.screen == "settings":
        render_settings()
    else:
        render_chat()


main()
