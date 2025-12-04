import flet as ft
import requests
import threading
import time
from datetime import datetime
import logging

# --- إعدادات السجلات ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- الثوابت الافتراضية (تم التحديث حسب طلبك) ---
DEFAULT_LAPTOP_IP = "192.168.1.6"  # العنوان الجديد للابتوب
DEFAULT_TERMUX_IP = "127.0.0.1"    # العنوان المحلي للهاتف
DEFAULT_FAST_MODEL = "qwen:0.5b"
DEFAULT_SMART_MODEL = "gemma:2b"
DEFAULT_THINKER_REMOTE = "qwen2.5:4b"

# --- طبقة الشبكة (Network Layer) ---
class AIConnector:
    @staticmethod
    def ping_server(url_base):
        """فحص سريع للاتصال (Health Check)"""
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            # نرسل طلب خفيف للجذر
            requests.get(f"{url_base}:11434", timeout=1)
            return True
        except:
            return False

    @staticmethod
    def send_request(url_base, model, prompt, timeout):
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            url = f"{url_base}:11434/api/generate"
            payload = {"model": model, "prompt": prompt, "stream": False, "options": {"num_ctx": 4096}}
            
            logging.info(f"Connecting to {url}...")
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return True, response.json().get("response", "")
        except requests.exceptions.Timeout:
            return False, "⚠️ المهلة انتهت! الخادم لم يستجب في الوقت المحدد."
        except requests.exceptions.ConnectionError:
            return False, "❌ تعذر الاتصال بالخادم. تأكد من تشغيل 'ollama serve' ومن صحة الـ IP."
        except Exception as e:
            return False, f"حدث خطأ غير متوقع: {str(e)}"

def main(page: ft.Page):
    # --- إعدادات الصفحة الأساسية ---
    page.title = "AI Nexus V2.1"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e0e0e"
    page.padding = 0

    # --- إدارة الحالة (State Management) ---
    termux_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.RED_900, size=12)
    laptop_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.RED_900, size=12)
    
    # استرجاع الإعدادات أو استخدام الافتراضي الجديد
    stored_laptop = page.client_storage.get("laptop_ip")
    stored_termux = page.client_storage.get("termux_ip")
    
    # حقول الإدخال (Text Fields)
    laptop_ip_input = ft.TextField(label="Laptop IP", value=stored_laptop if stored_laptop else DEFAULT_LAPTOP_IP, border_color=ft.Colors.BLUE_400)
    termux_ip_input = ft.TextField(label="Termux IP (Local)", value=stored_termux if stored_termux else DEFAULT_TERMUX_IP, border_color=ft.Colors.GREEN_400)
    
    fast_model_input = ft.TextField(label="النموذج السريع", value=page.client_storage.get("fast_model") or DEFAULT_FAST_MODEL, text_size=12)
    smart_model_input = ft.TextField(label="المفكر المحلي", value=page.client_storage.get("smart_model") or DEFAULT_SMART_MODEL, text_size=12)
    remote_model_input = ft.TextField(label="المفكر العملاق", value=page.client_storage.get("remote_model") or DEFAULT_THINKER_REMOTE, text_size=12)

    # --- مراقب الشبكة (Background Thread) ---
    def health_check_loop():
        while True:
            # نجلب القيم الحالية من الحقول مباشرة
            # ملاحظة: الوصول لقيم الواجهة من خيط آخر قد يكون خطراً، لذا نستخدم try
            try:
                t_ip = termux_ip_input.value
                l_ip = laptop_ip_input.value
                
                # تحديث Termux LED
                if AIConnector.ping_server(t_ip):
                    termux_led.color = ft.Colors.GREEN_ACCENT_400
                    termux_led.tooltip = "Termux: متصل"
                else:
                    termux_led.color = ft.Colors.RED_900
                    termux_led.tooltip = "Termux: غير متصل"

                # تحديث Laptop LED
                if AIConnector.ping_server(l_ip):
                    laptop_led.color = ft.Colors.BLUE_ACCENT_400
                    laptop_led.tooltip = "Laptop: متصل"
                else:
                    laptop_led.color = ft.Colors.RED_900
                    laptop_led.tooltip = "Laptop: غير متصل"
                
                page.update()
            except Exception as e:
                logging.error(f"Health Check Error: {e}")
            
            time.sleep(8) # فحص كل 8 ثواني

    threading.Thread(target=health_check_loop, daemon=True).start()

    # --- نافذة الإعدادات (The Dialog) ---
    def close_settings(e):
        page.close(settings_dialog)

    def save_settings(e):
        page.client_storage.set("laptop_ip", laptop_ip_input.value)
        page.client_storage.set("termux_ip", termux_ip_input.value)
        page.client_storage.set("fast_model", fast_model_input.value)
        page.client_storage.set("smart_model", smart_model_input.value)
        page.client_storage.set("remote_model", remote_model_input.value)
        
        page.close(settings_dialog)
        page.snack_bar = ft.SnackBar(content=ft.Text("تم حفظ الإعدادات وتحديث الشبكة"), bgcolor=ft.Colors.GREEN)
        page.open(page.snack_bar)
        page.update()

    # محتوى النافذة
    settings_content = ft.Column([
        ft.Text("إعدادات الاتصال", weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_200),
        laptop_ip_input,
        termux_ip_input,
        ft.Divider(),
        ft.ExpansionTile(
            title=ft.Text("تخصيص النماذج", size=14),
            leading=ft.Icon(ft.Icons.MEMORY, color=ft.Colors.GREY_400),
            controls=[
                ft.Container(
                    content=ft.Column([fast_model_input, smart_model_input, remote_model_input], spacing=10),
                    padding=10
                )
            ]
        )
    ], height=400, width=300, scroll=ft.ScrollMode.AUTO)

    settings_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("لوحة التحكم"),
        content=settings_content,
        actions=[
            ft.TextButton("إلغاء", on_click=close_settings),
            ft.ElevatedButton("حفظ", on_click=save_settings, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def open_settings(e):
        page.open(settings_dialog)

    # --- واجهة المحادثة (Chat UI) ---
    chat_list = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)
    loading_indicator = ft.ProgressBar(width=None, color=ft.Colors.CYAN_300, bgcolor=ft.Colors.TRANSPARENT, visible=False)

    def add_chat_bubble(text, sender="user", is_error=False):
        align = ft.MainAxisAlignment.END if sender == "user" else ft.MainAxisAlignment.START
        if sender == "user":
            bg_color = ft.Colors.BLUE_800
        elif is_error:
            bg_color = ft.Colors.RED_900
        else:
            bg_color = ft.Colors.GREY_800

        bubble = ft.Container(
            content=ft.Markdown(text, selectable=True, extension_set="standard"),
            padding=15,
            border_radius=ft.border_radius.only(
                top_left=15, top_right=15, 
                bottom_left=15 if sender == "user" else 0,
                bottom_right=0 if sender == "user" else 15
            ),
            bgcolor=bg_color,
            # تحديد عرض أقصى لجمالية الفقاعة
            width=300 if len(text) > 50 else None, 
        )
        chat_list.controls.append(ft.Row([bubble], alignment=align))
        page.update()

    # --- المنطق الرئيسي (The Core Logic) ---
    def process_request(prompt):
        loading_indicator.visible = True
        page.update()
        
        # قراءة القيم الحالية لحظة الإرسال
        l_ip = laptop_ip_input.value
        t_ip = termux_ip_input.value
        fast_m = fast_model_input.value
        smart_m = smart_model_input.value
        remote_m = remote_model_input.value

        response_text = ""
        is_error = False
        lower_prompt = prompt.lower()
        
        # 1. المسار السريع
        if "ساعة" in lower_prompt or "تاريخ" in lower_prompt:
            response_text = f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # 2. مسار التفكير العميق
        elif any(k in prompt for k in ["فكر", "بعمق", "خطط", "تحليل"]):
            success, resp = AIConnector.send_request(
                l_ip, remote_m, 
                f"أنت مهندس خبير. فكر بعمق وتفصيل ممل. السؤال: {prompt}", 300
            )
            if success:
                response_text = f"🧠 **(المفكر العملاق):**\n\n{resp}"
            else:
                response_text += f"⚠️ **فشل اللابتوب، جاري تشغيل المفكر المحلي...**\n\n"
                success_local, resp_local = AIConnector.send_request(
                    t_ip, smart_m, 
                    f"فكر بعمق: {prompt}", 120
                )
                if success_local:
                    response_text += f"📱 **(المفكر المحلي):**\n{resp_local}"
                else:
                    response_text += f"❌ **فشل كلي:** {resp_local}"
                    is_error = True
        
        # 3. المسار العادي
        else:
            success, resp = AIConnector.send_request(t_ip, fast_m, prompt, 60)
            if success:
                response_text = resp
            else:
                response_text = f"❌ خطأ محلي: {resp}"
                is_error = True

        loading_indicator.visible = False
        add_chat_bubble(response_text, "bot", is_error)

    def on_send_click(e):
        prompt = input_field.value
        if not prompt: return
        input_field.value = ""
        add_chat_bubble(prompt, "user")
        threading.Thread(target=process_request, args=(prompt,), daemon=True).start()
        input_field.focus()

    # --- تجميع الواجهة ---
    input_field = ft.TextField(
        hint_text="تحدث مع مساعدك...",
        border_radius=30,
        bgcolor=ft.Colors.GREY_900,
        border_color=ft.Colors.TRANSPARENT,
        expand=True,
        on_submit=on_send_click
    )

    page.appbar = ft.AppBar(
        title=ft.Row([
            ft.Text("AI Hybrid", weight=ft.FontWeight.BOLD),
            ft.Container(width=10),
            ft.Tooltip(message="حالة Termux", content=termux_led),
            ft.Tooltip(message="حالة Laptop", content=laptop_led),
        ]),
        bgcolor=ft.Colors.GREY_900,
        actions=[ft.IconButton(ft.Icons.SETTINGS, on_click=open_settings)],
    )

    page.add(
        ft.Column([
            chat_list,
            ft.Container(loading_indicator, height=5),
            ft.Container(
                content=ft.Row([
                    input_field,
                    ft.FloatingActionButton(icon=ft.Icons.SEND, on_click=on_send_click, bgcolor=ft.Colors.BLUE_600)
                ]),
                padding=10,
                bgcolor=ft.Colors.GREY_950
            )
        ], expand=True)
    )

ft.app(target=main)