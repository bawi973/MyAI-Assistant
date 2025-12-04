import flet as ft
import onnxruntime
import numpy as np
import os
import difflib
import threading
import time
import requests # للتحميل
from datetime import datetime
from tokenizers import Tokenizer

# --- روابط التحميل (المصدر) ---
# رابط مباشر لملف ONNX المخفف من HuggingFace
MODEL_URL = "https://huggingface.co/onnx-community/Qwen2.5-0.5B-Instruct/resolve/main/onnx/model_quantized.onnx"
MODEL_FILENAME = "model_quantized.onnx"

# --- إعدادات المسارات ---
# سنحفظ النموذج في مجلد التطبيق الداخلي في الهاتف
def get_model_path():
    # في الأندرويد، نحفظ في مجلد المستندات أو البيانات
    return os.path.join(os.getcwd(), MODEL_FILENAME)

# --- الدماغ الأول: الذاكرة السريعة ---
class LocalBrain:
    def __init__(self):
        self.memory = {
            "مرحبا": "أهلاً بك! جاري تجهيز الذكاء الاصطناعي...",
            "من انت": "أنا تطبيق Qwen-Native، أعمل بمعالج هاتفك.",
        }
    
    def learn(self, q, a):
        self.memory[q.lower().strip()] = a

    def get_response(self, text):
        text = text.lower().strip().replace("أ", "ا").replace("ة", "ه")
        if "ساعه" in text or "وقت" in text:
            return f"⏰ {datetime.now().strftime('%I:%M %p')}"
        
        matches = difflib.get_close_matches(text, self.memory.keys(), n=1, cutoff=0.7)
        if matches: return self.memory[matches[0]]
        return None

# --- الدماغ الثاني: محرك Qwen ---
class QwenEngine:
    def __init__(self):
        self.session = None
        self.tokenizer = None
        self.status = "جاري الفحص..."
        self.progress = 0.0
        self.is_downloading = False
        self.is_ready = False
        
        # نبدأ عملية الفحص والتحميل
        threading.Thread(target=self._init_system, daemon=True).start()

    def _init_system(self):
        try:
            target_path = get_model_path()
            
            # 1. تحميل التوكينايزر (موجود في assets التطبيق)
            # Flet يفك ضغط الـ assets عند التشغيل، نحاول قراءته
            try:
                self.tokenizer = Tokenizer.from_file("assets/tokenizer.json")
            except:
                self.status = "⚠️ ملف Tokenizer مفقود في Assets"
                return

            # 2. فحص وجود النموذج
            if not os.path.exists(target_path):
                self.status = "جاري تحميل النموذج (مرة واحدة فقط)..."
                self.is_downloading = True
                self._download_model(target_path)
                self.is_downloading = False
            
            if not os.path.exists(target_path):
                self.status = "❌ فشل التحميل."
                return

            # 3. تشغيل النموذج
            self.status = "جاري تحميل النموذج إلى المعالج..."
            
            # إعدادات لتسريع المعالج
            sess_options = onnxruntime.SessionOptions()
            sess_options.intra_op_num_threads = 4 
            sess_options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
            sess_options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = onnxruntime.InferenceSession(
                target_path, 
                sess_options=sess_options, 
                providers=['CPUExecutionProvider']
            )
            
            self.is_ready = True
            self.status = "✅ جاهز (Qwen Native)"
            
        except Exception as e:
            self.status = f"خطأ: {str(e)}"

    def _download_model(self, save_path):
        try:
            response = requests.get(MODEL_URL, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024 * 1024 # 1 MB chunk
            downloaded = 0

            with open(save_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    f.write(data)
                    downloaded += len(data)
                    if total_size > 0:
                        self.progress = downloaded / total_size
            
            self.progress = 1.0
        except Exception as e:
            self.status = f"فشل التحميل: {e}"
            if os.path.exists(save_path): os.remove(save_path) # حذف الملف المعطوب

    def generate(self, text):
        if not self.is_ready: return f"⚠️ {self.status}"
        
        try:
            # تجهيز النص
            prompt = f"<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
            tokens = self.tokenizer.encode(prompt).ids
            
            input_feed = {self.session.get_inputs()[0].name: np.array([tokens], dtype=np.int64)}
            
            # تشغيل الاستنتاج
            output = self.session.run(None, input_feed)[0]
            
            # استخراج الكلمة (للتبسيط نأخذ كلمة واحدة، التوليد الكامل يحتاج Loop)
            predicted_id = np.argmax(output[0, -1, :])
            decoded = self.tokenizer.decode([predicted_id])
            
            return f"🤖 (Qwen): {decoded}... (تمت المعالجة محلياً)"
            
        except Exception as e:
            return f"خطأ المعالجة: {e}"

def main(page: ft.Page):
    page.title = "Qwen Downloader"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#111"

    local_brain = LocalBrain()
    qwen_engine = QwenEngine()
    
    chat = ft.ListView(expand=True, spacing=10, padding=15, auto_scroll=True)
    
    # عناصر شريط الحالة والتحميل
    status_lbl = ft.Text("...", color="grey", size=12)
    progress_bar = ft.ProgressBar(width=200, color="blue", visible=False)

    def update_ui_loop():
        while True:
            status_lbl.value = qwen_engine.status
            
            if qwen_engine.is_downloading:
                progress_bar.visible = True
                progress_bar.value = qwen_engine.progress
                status_lbl.value = f"جاري التحميل: {int(qwen_engine.progress * 100)}%"
            else:
                progress_bar.visible = False
                status_lbl.color = "green" if qwen_engine.is_ready else "red"
            
            page.update()
            time.sleep(0.5)

    threading.Thread(target=update_ui_loop, daemon=True).start()

    def add(text, sender):
        align = ft.MainAxisAlignment.END if sender == "user" else ft.MainAxisAlignment.START
        bg = ft.Colors.BLUE_900 if sender == "user" else ft.Colors.GREY_800
        chat.controls.append(ft.Row([ft.Container(content=ft.Markdown(text), padding=12, border_radius=10, bgcolor=bg)], alignment=align))
        page.update()

    def send(e):
        txt = field.value
        if not txt: return
        field.value = ""
        add(txt, "user")

        # الرد الفوري
        fast = local_brain.get_response(txt)
        if fast:
            add(fast, "bot")
            return

        # الرد العميق
        loading = ft.ProgressRing(width=20, height=20)
        chat.controls.append(loading)
        page.update()
        
        def run():
            resp = qwen_engine.generate(txt)
            chat.controls.remove(loading)
            add(resp, "bot")
        threading.Thread(target=run, daemon=True).start()

    field = ft.TextField(hint_text="تحدث...", expand=True, on_submit=send, border_radius=20, bgcolor="#222")
    
    page.add(
        ft.Container(
            content=ft.Column([
                ft.Row([ft.Text("Native AI", weight="bold"), ft.Container(expand=True), status_lbl]),
                progress_bar
            ]), 
            padding=10, bgcolor="#222"
        ),
        ft.Container(chat, expand=True),
        ft.Container(content=ft.Row([field, ft.IconButton(ft.Icons.SEND, on_click=send)]), padding=10)
    )

ft.app(target=main)