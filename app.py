import requests
import streamlit as st
from datetime import datetime
from openai import OpenAI
from streamlit_cookies_manager import EncryptedCookieManager

# =========================================================
# 1. 페이지 기본 설정 및 디자인 테마
# =========================================================
st.set_page_config(
    page_title="닥터 펫: 동물 가상 의료 상담소", 
    page_icon="🦜", 
    layout="wide"
)

st.markdown(
    """
    <style>
    /* 1. 전체 배경: 따뜻한 살구색/베이지 톤 (병원 벽면 느낌) */
    .stApp {
        background-color: #FDF3E9;
    }

    /* 2. 로그인 폼 스크롤바 방지 및 여백 최적화 */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab-panel"] {
        min-height: 360px;
    }
    .stTextInput {
        margin-bottom: 0.2rem;
    }
    
    /* 3. 텍스트 입력창 우측 'Press Enter to apply' 영어 문구 숨기기 */
    div[data-testid="InputInstructions"] {
        display: none !important;
    }

    /* 4. 사이드바: 접수처 데스크 느낌의 민트 톤 */
    [data-testid="stSidebar"] {
        background-color: #79DCD0 !important; 
    }
    [data-testid="stSidebar"] * {
        font-size: 1.05rem !important; 
        color: #26403C !important; /* 텍스트는 가독성 좋은 짙은 청록색 */
    }
    [data-testid="stSidebar"] h1 {
        font-size: 1.8rem !important;
        font-weight: bold;
        color: #1A2F2B !important;
        margin-bottom: 1rem;
    }
    
    /* 5. 진료 폼 & 기록장 (카드 형태의 병원 차트 느낌) */
    div[data-testid="stForm"], div[data-testid="stExpander"] {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0px 4px 15px rgba(0, 0, 0, 0.05); /* 부드러운 그림자 */
        border-top: 5px solid #79DCD0; /* 상단에 민트색 포인트 줄 */
        margin-bottom: 20px;
    }

    /* 6. 닥터 펫 전용 텍스트 스타일 (헤더) */
    .main-header {
        font-size: 28px;
        font-weight: bold;
        color: #26403C;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 16px;
        color: #666666;
        margin-bottom: 20px;
    }

    /* 7. 채팅 말풍선 및 디자인 최적화 */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF;
        border-radius: 15px;
        padding: 15px 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.04);
        margin-bottom: 15px;
        border-left: 5px solid #79DCD0; /* 말풍선 왼쪽 민트색 포인트 */
    }

    /* 8. 버튼 스타일링 (포인트 컬러 적용) */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #79DCD0;
        color: #26403C;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        border: 1px solid #79DCD0;
        background-color: #79DCD0;
        color: white;
    }

    /* 9. 로그인 및 텍스트 입력창 배경을 완전한 흰색으로 변경 */
    .stTextInput div[data-baseweb="input"] {
        background-color: #FFFFFF !important;
        border-radius: 8px !important;
        border: 1px solid #CCCCCC !important;
    }
    /* 입력창 클릭(포커스) 시 테두리가 민트색으로 변하게 포인트 추가 */
    .stTextInput div[data-baseweb="input"]:focus-within {
        border: 2px solid #79DCD0 !important;
    }
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #26403C !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# 2. Firebase REST API 및 Upstage API 설정
# =========================================================
API_KEY = "AIzaSyC7EiUsz6GD807ZWLAnE7YGd7kFw2Qo1hg"
DATABASE_URL = "https://test-c243e-default-rtdb.asia-southeast1.firebasedatabase.app"

def sanitize_email(email):
    return email.replace(".", ",")

# Pyrebase 대체용 Requests 기반 Firebase 헬퍼 클래스
class FirebaseResponse:
    def __init__(self, data):
        self._data = data
    def val(self):
        return self._data

class FirebaseAuth:
    @staticmethod
    def sign_in_with_email_and_password(email, password):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            return res.json()
        else:
            raise Exception(res.json().get("error", {}).get("message", "Login failed"))

    @staticmethod
    def create_user_with_email_and_password(email, password):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            return res.json()
        else:
            raise Exception(res.json().get("error", {}).get("message", "Signup failed"))

    @staticmethod
    def send_email_verification(id_token):
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={API_KEY}"
        payload = {"requestType": "VERIFY_EMAIL", "idToken": id_token}
        res = requests.post(url, json=payload)
        return res.json()

    @staticmethod
    def refresh(refresh_token):
        url = f"https://securetoken.googleapis.com/v1/token?key={API_KEY}"
        payload = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        res = requests.post(url, json=payload)
        if res.status_code == 200:
            data = res.json()
            return {"refreshToken": data["refresh_token"], "idToken": data["id_token"]}
        else:
            raise Exception("Token refresh failed")

class FirebaseDB:
    def __init__(self, path=""):
        self.path = path

    def child(self, name):
        new_path = f"{self.path}/{name}" if self.path else name
        return FirebaseDB(new_path)

    def set(self, data):
        url = f"{DATABASE_URL}/{self.path}.json"
        res = requests.put(url, json=data)
        return res.json()

    def push(self, data):
        url = f"{DATABASE_URL}/{self.path}.json"
        res = requests.post(url, json=data)
        return res.json()

    def update(self, data):
        url = f"{DATABASE_URL}/{self.path}.json"
        res = requests.patch(url, json=data)
        return res.json()

    def get(self):
        url = f"{DATABASE_URL}/{self.path}.json"
        res = requests.get(url)
        return FirebaseResponse(res.json())

    def remove(self):
        url = f"{DATABASE_URL}/{self.path}.json"
        res = requests.delete(url)
        return res.json()

db = FirebaseDB()
auth = FirebaseAuth()

UPSTAGE_API_KEY = "up_Y7OKHBUB2q7pi7C4E1ILIWItBAUOG" 
client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v1"
)

# =========================================================
# 3. 로그인 유지용 쿠키 매니저 설정
# =========================================================
cookies = EncryptedCookieManager(
    prefix="doctor_pet/",
    password="doctor-pet-please-change-this-secret",
)
if not cookies.ready():
    st.stop()

# =========================================================
# 4. 세션 상태 초기화 (+ 쿠키 기반 로그인 복원)
# =========================================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pet_info" not in st.session_state:
    st.session_state.pet_info = None
if "auth_restored" not in st.session_state:
    st.session_state.auth_restored = False

if not st.session_state.logged_in and not st.session_state.auth_restored:
    st.session_state.auth_restored = True
    saved_refresh_token = cookies.get("refresh_token")
    saved_email = cookies.get("user_email")

    if saved_refresh_token and saved_email:
        try:
            refreshed_user = auth.refresh(saved_refresh_token)
            st.session_state.logged_in = True
            st.session_state.user_email = saved_email
            cookies["refresh_token"] = refreshed_user["refreshToken"]
            cookies.save()
        except Exception:
            cookies["user_email"] = ""
            cookies["refresh_token"] = ""
            cookies.save()

# =========================================================
# 5. 앱 화면 분기 (로그인 안 됨 -> 로그인 UI / 로그인 됨 -> 메인 앱 UI)
# =========================================================
if not st.session_state.logged_in:
    st.markdown("<h3 style='text-align: center; margin-bottom: 15px; color: #26403C;'>🔐 닥터 펫 로그인</h3>", unsafe_allow_html=True)

    _, col_center, _ = st.columns([1, 2, 1])

    with col_center:
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

        with tab_login:
            st.write("") 
            login_email = st.text_input("이메일", key="login_email")
            login_pw = st.text_input("비밀번호", type="password", key="login_pw")
            st.write("")
            
            if st.button("로그인", key="login_btn", use_container_width=True):
                if not login_email or not login_pw:
                    st.warning("이메일과 비밀번호를 모두 입력해주세요.")
                else:
                    try:
                        user = auth.sign_in_with_email_and_password(login_email, login_pw)
                        st.session_state.logged_in = True
                        st.session_state.user_email = login_email

                        cookies["user_email"] = login_email
                        cookies["refresh_token"] = user["refreshToken"]
                        cookies.save()

                        st.success("로그인 성공!")
                        st.rerun()
                    except Exception as e:
                        st.error("로그인 실패: 이메일 또는 비밀번호를 확인해주세요.")

        with tab_signup:
            st.write("") 
            signup_email = st.text_input("사용할 이메일", key="signup_email")
            signup_pw = st.text_input("사용할 비밀번호 (6자 이상)", type="password", key="signup_pw")
            signup_pw_confirm = st.text_input("비밀번호 확인", type="password", key="signup_pw_confirm")
            st.write("")
            
            if st.button("계정 생성", key="signup_btn", use_container_width=True):
                if not signup_email or not signup_pw or not signup_pw_confirm:
                    st.warning("모든 항목을 입력해주세요.")
                elif signup_pw != signup_pw_confirm:
                    st.error("비밀번호가 서로 일치하지 않습니다.")
                else:
                    try:
                        user = auth.create_user_with_email_and_password(signup_email, signup_pw)
                        auth.send_email_verification(user['idToken'])
                        
                        safe_email = sanitize_email(signup_email)
                        db.child("users").child(safe_email).set({
                            "email": signup_email,
                            "status": "active",
                        })
                        st.success("회원가입 성공! 입력하신 메일로 인증 메일이 발송되었습니다. 메일함이 오지 않았다면 **스팸메일함**을 꼭 확인해주세요!")
                    except Exception as e:
                        st.error("회원가입 실패: 이미 가입된 이메일이거나 비밀번호가 너무 짧습니다.")

else:
    with st.sidebar:
        with st.container(border=True):
            st.caption("현재 접속 계정")
            st.markdown(f"👤 **{st.session_state.user_email}**")
            if st.button("로그아웃", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user_email = ""
                st.session_state.messages = []
                st.session_state.pet_info = None
                st.session_state.auth_restored = False

                cookies["user_email"] = ""
                cookies["refresh_token"] = ""
                cookies.save()

                st.rerun()
                
        st.markdown("---")
        st.title("🏥 닥터 펫 메뉴")
        menu = st.radio("", ["🩺 AI 실시간 의료 상담", "📅 털갈이/탈피 주기 기록 & 영양제"], label_visibility="collapsed")
        st.info("💡 **특수 동물 보호자를 위한 공간**\n\n강아지·고양이가 아니어도 괜찮아요. 우리 아이들의 건강을 세심하게 챙겨드립니다.")

    if menu == "🩺 AI 실시간 의료 상담":
        st.markdown('<p class="main-header">🦜 닥터 펫: 특수 동물 가상 의료 상담소</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">흔하지 않은 반려동물을 위한 맞춤형 진료 및 건강 상담을 시작합니다.</p>', unsafe_allow_html=True)

        if st.session_state.pet_info is None:
            with st.form("pet_info_form"):
                st.subheader("📝 우리 아이 기본 정보를 알려주세요!")
                col1, col2 = st.columns(2)
                with col1:
                    guardian_name = st.text_input("보호자 성함")
                    animal_type = st.text_input("동물 종류 (예: 앵무새, 고슴도치, 파충류 등)")
                with col2:
                    animal_name = st.text_input("동물의 이름")
                    animal_age = st.text_input("동물의 나이")

                submitted = st.form_submit_button("진료실 들어가기")
                
                if submitted:
                    if guardian_name and animal_type and animal_name and animal_age:
                        st.session_state.pet_info = {
                            "guardian": guardian_name,
                            "type": animal_type,
                            "name": animal_name,
                            "age": animal_age,
                        }

                        system_prompt = (
                            "당신은 앵무새, 고슴도치, 파충류 등 흔하지 않은 특수 동물들을 전문적으로 진료하는 따뜻하고 유능한 가상 수의사 '닥터 펫'입니다. "
                            f"현재 보호자 {guardian_name}님이 키우시는 {animal_type} (이름: {animal_name}, 나이: {animal_age})가 진료실에 들어왔습니다. "
                            "보호자에게 첫인사를 건네며, '오늘 어떤 증상 때문에 찾아오셨나요?' 혹은 '어디가 불편해서 왔을까요?'라고 따뜻하게 질문하며 상담을 이끌어주세요."
                        )

                        st.session_state.messages.append({"role": "system", "content": system_prompt})
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"안녕하세요, {guardian_name} 보호자님! 🦜\n\n{animal_type} '{animal_name}'의 주치의 닥터 펫입니다. 우리 {animal_name}(이)가 오늘 어디가 불편해서 찾아왔을까요? 편하게 증상을 말씀해 주세요!"
                        })
                        st.rerun()
                    else:
                        st.warning("모든 칸을 빠짐없이 채워주세요!")
                        
        else:
            info = st.session_state.pet_info
            st.success(f"🏥 현재 진료 중: **{info['type']} ({info['name']}, {info['age']})** | 보호자: {info['guardian']}님")

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔄 다른 환자 진료하기 (정보 초기화)"):
                    st.session_state.pet_info = None
                    st.session_state.messages = []
                    st.rerun()
            with col2:
                if st.button("🧹 대화 내용만 초기화"):
                    system_msg = st.session_state.messages[0]
                    st.session_state.messages = [
                        system_msg,
                        {
                            "role": "assistant",
                            "content": f"대화가 초기화되었습니다. {info['name']}(이)의 증상을 다시 편하게 말씀해 주세요!"
                        },
                    ]
                    st.rerun()

            for message in st.session_state.messages:
                if message["role"] != "system":
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

            prompt = st.chat_input("증상이나 궁금한 점을 편하게 입력해 주세요.")
            if prompt:
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    stream = client.chat.completions.create(
                        model="solar-pro",
                        messages=st.session_state.messages,
                        stream=True
                    )

                    def generate_response():
                        for chunk in stream:
                            if chunk.choices:
                                content = chunk.choices[0].delta.content
                                if content:
                                    yield content

                    response = st.write_stream(generate_response())

                st.session_state.messages.append({"role": "assistant", "content": response})

    elif menu == "📅 털갈이/탈피 주기 기록 & 영양제":
        st.markdown('<p class="main-header">📅 털갈이/탈피 주기 기록 및 맞춤 케어</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">우리 아이의 주기적인 신체 변화를 기록하고, 상태에 맞는 맞춤 영양제를 추천받으세요.</p>', unsafe_allow_html=True)

        safe_email = sanitize_email(st.session_state.user_email)

        with st.form("care_log_form"):
            st.subheader("📝 새로운 주기 기록 남기기")
            log_date = st.date_input("기록 날짜", datetime.now())
            log_status = st.text_input("아이의 현재 상태 (예: 깃털이 유독 많이 빠짐, 탈피 시작 등)")
            log_photo_desc = st.text_area("특이사항 및 메모 (예: 울음소리가 쉰 듯하고 변이 무름)")

            submitted_log = st.form_submit_button("기록 저장하기")
            if submitted_log:
                if log_status:
                    with st.spinner("기록을 안전하게 저장하는 중입니다..."):
                        recommendation = "종합 비타민 및 미네랄 보조제"
                        if "깃털" in log_status or "탈피" in log_status:
                            recommendation = "단백질 및 케라틴 합성을 위한 아미노산/깃털 전용 영양제, 칼슘제"
                        elif "기운" in log_status or "쉰" in log_status:
                            recommendation = "면역력 강화용 유산균 및 비타민 B군"

                        new_log = {
                            "date": str(log_date),
                            "status": log_status,
                            "memo": log_photo_desc,
                            "recommendation": recommendation,
                        }
                        
                        db.child("users").child(safe_email).child("care_logs").push(new_log)
                    
                    st.success("성공적으로 기록되었습니다!")
                    st.rerun()
                else:
                    st.warning("아이의 현재 상태를 간략히라도 입력해주세요!")

        st.markdown("---")
        st.subheader("📂 우리 아이 건강 기록장")

        logs_data = db.child("users").child(safe_email).child("care_logs").get()
        care_logs_list = []
        
        if logs_data.val() is not None:
            for key, value in logs_data.val().items():
                value["firebase_key"] = key
                care_logs_list.append(value)

        if len(care_logs_list) == 0:
            st.info("아직 저장된 기록이 없습니다. 위에서 첫 기록을 남겨보세요!")
        else:
            for log in reversed(care_logs_list):
                log_key = log["firebase_key"]
                with st.expander(f"📌 기록일: {log['date']} - 상태: {log['status']}"):
                    
                    with st.form(key=f"edit_form_{log_key}"):
                        st.markdown("##### ✏️ 기록 수정하기")
                        edited_status = st.text_input("상태 수정", value=log['status'])
                        edited_memo = st.text_area("메모 수정", value=log['memo'])
                        
                        col_update, col_delete = st.columns(2)
                        
                        with col_update:
                            update_submitted = st.form_submit_button("💾 수정 저장", use_container_width=True)
                        with col_delete:
                            delete_submitted = st.form_submit_button("🗑️ 기록 삭제", use_container_width=True)

                        if update_submitted:
                            with st.spinner("수정 내용을 반영하는 중입니다..."):
                                recommendation = "종합 비타민 및 미네랄 보조제"
                                if "깃털" in edited_status or "탈피" in edited_status:
                                    recommendation = "단백질 및 케라틴 합성을 위한 아미노산/깃털 전용 영양제, 칼슘제"
                                elif "기운" in edited_status or "쉰" in edited_status:
                                    recommendation = "면역력 강화용 유산균 및 비타민 B군"

                                updated_data = {
                                    "date": log['date'],
                                    "status": edited_status,
                                    "memo": edited_memo,
                                    "recommendation": recommendation
                                }
                                db.child("users").child(safe_email).child("care_logs").child(log_key).update(updated_data)
                            st.success("기록이 수정되었습니다!")
                            st.rerun()

                        if delete_submitted:
                            with st.spinner("기록을 삭제하는 중입니다..."):
                                db.child("users").child(safe_email).child("care_logs").child(log_key).remove()
                            st.success("기록이 삭제되었습니다!")
                            st.rerun()

                    st.markdown("---")
                    st.success(f"💡 **닥터 펫 맞춤 처방 및 추천 영양제:** {log['recommendation']}")
