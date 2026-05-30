<<<<<<< HEAD

import traceback
import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# 1. 프롬프트 개선 (출력 형식을 조금 더 명확하게 지시)
SUMMARIZE_PROMPT = """다음 제공된 콘텐츠의 핵심 내용을 약 300자 내외로 알기 쉽게 요약해주세요.
반드시 한국어로 자연스럽게 작성해야 합니다.

========
{content}
========
"""

def init_page():
    st.set_page_config(page_title="웹 사이트 요약기", page_icon="🤗")
    st.header("웹 사이트 요약기 🤗")
    st.sidebar.title("Options")

def select_model(temperature = 0):
    models = ("gpt-5.5", "gpt-5.4-mini")
    model = st.sidebar.radio("Choose a model:", models)
    if model == 'gpt-5.5':
        return ChatOpenAI(temperature = temperature, model = 'gpt-5.5')
    else:
        return ChatOpenAI(temperature = temperature, model = 'gpt-5.4-mini')

def init_chain():
    llm = select_model()
    prompt = ChatPromptTemplate.from_messages([
        ('user', SUMMARIZE_PROMPT)])
    chain = prompt | llm | StrOutputParser()
    return chain

def get_content(url):
    with st.spinner('웹 사이트 정보 찾는중...'):
        url = requests.get(url)
        html = BeautifulSoup(url.text)
        if html.main:
            return html.main.text
        elif html.article:
            return html.article.text
        else:
            return html.body.text

def main():
    init_page()
    chain = init_chain()
    if url := st.text_input("URL: ", key = 'input'):
        if content := get_content(url):
            st.markdown("## Summary")
            st.write_stream(chain.stream({'content' : content}))
            st.markdown("-----")
            st.markdown("## Original Text")
            st.write(content)

main()
=======

import tiktoken
import streamlit as st
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser

# models
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL_PRICES = {
    "input": {
        "gpt-5.5": 5 / 1_000_000,
        "gpt-5.4-mini": 0.75 / 1_000_000
    },
    "output": {
        "gpt-5.5": 30 / 1_000_000,
        "gpt-5.4-mini": 4.5 / 1_000_000
    },
}

SYSTEM_PROMPT = "당신은 친절하고 유용한 도움을 주는 어시스턴트입니다."

def init_page():
    st.set_page_config(page_title="My ChatGPT", page_icon="🤗")
    st.header("My ChatGPT 🤗")
    st.sidebar.title("Options")

def init_messages():
    clear_button = st.sidebar.button("Clear Conversation", key="clear")
    if clear_button or "message_history" not in st.session_state:
        st.session_state.message_history = []

    # [수정] model_name이 세션에 없으면 기본값으로 미리 초기화해둡니다.
    if "model_name" not in st.session_state:
        st.session_state.model_name = "gpt-5.5"

def main():
    init_page()
    init_messages()

    # 사이드바에서 모델 및 하이퍼파라미터 선택 (체인 생성 전에 완료)
    llm = select_model()
    chain = init_chain(llm)

    # 대화 기록 렌더링
    for msg in st.session_state.message_history:
        st.chat_message(msg['role']).markdown(msg['content'])

    if user_input := st.chat_input("궁금한 내용을 입력해주세요."):

        with st.spinner("ChatGPT가 답변 중..."):

            st.session_state.message_history.append({'role' : "user", "content" : user_input})
            st.chat_message("user").markdown(user_input)

            with st.chat_message('assistant'):
                # LangChain 프롬프트에 들어갈 history 포맷을 튜플 형태로 변환하여 호환성 확보
                formatted_history = [(msg['role'], msg['content']) for msg in st.session_state.message_history[:-1]]

                response = st.write_stream(
                    chain.stream(
                        {
                            "history" : formatted_history,
                            "user_input" : user_input
                        }
                    )
                )

                st.session_state.message_history.append({'role' : 'assistant', 'content' : response})

    # 비용 계산 함수 호출
    calc_and_display_costs()

def select_model():
    temperature = st.sidebar.slider(
        "Temperature:", min_value=0.0, max_value=2.0, value=0.0, step=0.1
    )

    models = ("gpt-5.5", "gpt-5.4-mini")
    # 세션 상태를 index에 반영하여 위젯이 재렌더링되어도 선택이 유지되도록 설정
    default_index = models.index(st.session_state.model_name) if st.session_state.model_name in models else 0
    model = st.sidebar.radio("Choose a model:", models, index=default_index)

    st.session_state.model_name = model

    return ChatOpenAI(
        temperature=temperature,
        model=st.session_state.model_name,
    )

def get_message_counts(text):
    try:
        # 먼저 모델명으로 인코딩을 자동 탐색 시도
        encoding = tiktoken.encoding_for_model(st.session_state.model_name)
    except KeyError:
        # gpt-5.5 등 사전에 등록되지 않은 신규 모델명일 경우,
        # 최신 GPT 계열이 기본적으로 사용하는 'cl100k_base' (또는 상황에 따라 'o200k_base')를 강제로 지정
        encoding = tiktoken.get_encoding("cl100k_base")

    return len(encoding.encode(text))

def calc_and_display_costs():
    output_count = 0
    input_count = 0

    for msg in st.session_state.message_history:
        token_count = get_message_counts(msg['content'])
        if msg['role'] == 'assistant':
            output_count += token_count
        else:
            input_count += token_count

    cost_input = MODEL_PRICES['input'][st.session_state.model_name] * input_count
    cost_output = MODEL_PRICES['output'][st.session_state.model_name] * output_count
    cost = cost_input + cost_output

    st.sidebar.markdown("---")
    st.sidebar.markdown("## Costs")
    # 소수점 아래 자릿수가 너무 작아 0.00으로 보일 수 있으므로 포맷을 %.5f 정도로 유연하게 주거나 유지
    st.sidebar.markdown(f"**Total Cost: ${cost:.5f}**")
    st.sidebar.markdown(f"- Input Cost: ${cost_input:.5f}")
    st.sidebar.markdown(f"- Output Cost: ${cost_output:.5f}")

def init_chain(llm):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("user", "{user_input}"),
        ]
    )

    parser = StrOutputParser()
    return prompt | llm | parser

load_dotenv()

main()
>>>>>>> 729ba628e506fba2edd9f4ac0bf90741ff705d28
