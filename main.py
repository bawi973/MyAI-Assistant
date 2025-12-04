import flet as ft
import requests
import threading
from datetime import datetime
import logging

# --- إعدادات السجلات (Logging) للمحترفين لمراقبة الأخطاء ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- الثوابت الافتراضية ---
DEFAULT_LAPTOP_IP = "192.168.1.15"  # مثال
DEFAULT_TERMUX_IP = "127.0.0.1"     # سنحتاج لتغييره لعنوان الهاتف لاحقاً
DEFAULT_FAST_MODEL = "qwen:0.5b"
DEFAULT_SMART_MODEL = "gemma:2b"
DEFAULT_THINKER_REMOTE = "qwen2.5:4b"

# --- فئة لإدارة الاتصال (Network Layer) ---
class AIConnector:
    @staticmethod
    def send_request(url_base, model, prompt, timeout):
        try:
            # التأكد من البروتوكول (http://)
            if not url_base.startswith("http"):
                url_base = f"http://{url_base}"
            
            url = f"{url_base}:11434/api/generate"
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 4096}
            }
            logging.info(f"Connecting to {url} with model {model}...")
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return True, response.json().get("response", "")
        except requests.exceptions.Timeout:
            logging.error("Timeout Error")
            return False, "⚠️ المهلة انتهت! الخادم لم يستجب في الوقت المحدد."
        except requests.exceptions.ConnectionError:
            logging.error(f"Connection Error to {url_base}")
            return False, "❌ لا يمكن الوصول للخادم (تأكد من العنوان والتشغيل)."
        except Exception as e:
            logging.error(f"General Error: {e}")
            return False, f"حدث خطأ غير متوقع: {str(e)}"

def main(page: ft.Page):
    # --- إعدادات الواجهة العامة ---
    page.title = "AI Nexus"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0e0e0e"
    page.padding = 0
    
    # --- المتغيرات والحالة ---
    stored_laptop = page.client_storage.get("laptop_ip")
    stored_termux = page.client_storage.get("termux_ip")
    
    laptop_ip_input = ft.TextField(label="Laptop IP", value=stored_laptop if stored_laptop else DEFAULT_LAPTOP_IP)
    termux_ip_input = ft.TextField(label="Termux/Phone IP", value=stored_termux if stored_termux else DEFAULT_TERMUX_IP)
    
    chat_list = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)
    
    def handle_submit(e):
        send_message_click(None)

    input_field = ft.TextField(
        hint_text="اكتب هنا أو قل 'فكر معي'...",
        border_radius=30,
        bgcolor="#1f1f1f",
        border_color="#333",
        expand=True,
        multiline=False,
        on_submit=handle_submit 
    )

    # --- دوال الواجهة (UI Logic) ---
    def add_chat_bubble(text, sender="user", is_error=False):
        align = ft.MainAxisAlignment.END if sender == "user" else ft.MainAxisAlignment.START
        if sender == "user":
            bg_color = "#2196F3"
            text_color = "white"
        elif is_error:
            bg_color = "#CF6679"
            text_color = "black"
        else:
            bg_color = "#303030"
            text_color = "white"

        bubble = ft.Container(
            content=ft.Text(text, size=16, color=text_color, selectable=True),
            padding=15,
            border_radius=ft.border_radius.only(
                top_left=15, top_right=15, 
                bottom_left=15 if sender == "user" else 0,
                bottom_right=0 if sender == "user" else 15
            ),
            bgcolor=bg_color,
            width=None if len(text) < 50 else 300,
            animate_opacity=300,
        )
        chat_list.controls.append(ft.Row([bubble], alignment=align))
        page.update()

    def show_typing():
        loading = ft.Row([ft.ProgressRing(width=20, height=20, stroke_width=2), ft.Text(" جارِ المعالجة...", color="grey")], alignment=ft.MainAxisAlignment.START)
        chat_list.controls.append(loading)
        page.update()
        return loading

    def remove_typing(loading_control):
        if loading_control in chat_list.controls:
            chat_list.controls.remove(loading_control)
            page.update()

    # --- قلب النظام: المعالجة في الخلفية ---
    def process_request_background(prompt, laptop_ip, termux_ip, loading_control):
        response_text = ""
        is_error = False

        lower_prompt = prompt.lower()
        
        # 1. المسار السريع
        if "ساعة" in lower_prompt or "تاريخ" in lower_prompt:
            response_text = f"⏰ الوقت والتاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        elif "بطارية" in lower_prompt:
             response_text = "🔋 مستوى البطارية يتطلب صلاحيات إضافية."

        # 2. مسار التفكير العميق
        elif any(k in prompt for k in ["فكر", "بعمق", "خطط", "تحليل", "مهندس"]):
            success, resp = AIConnector.send_request(
                laptop_ip, 
                DEFAULT_THINKER_REMOTE, 
                f"أنت مهندس خبير ومفكر استراتيجي. فكر بعمق ولا تتسرع. السؤال: {prompt}", 
                timeout=300
            )
            if success:
                response_text = f"🧠 (سيرفر المفكر): \n{resp}"
            else:
                response_text += f"\n⚠️ فشل الاتصال بالسيرفر ({resp})... جاري التحويل للمستشار المحلي.\n"
                success_local, resp_local = AIConnector.send_request(
                    termux_ip,
                    DEFAULT_SMART_MODEL,
                    f"فكر بعمق في هذا السؤال: {prompt}",
                    timeout=120
                )
                if success_local:
                    response_text += f"📱 (المفكر المحلي): \n{resp_local}"
                else:
                    response_text += f"❌ فشل المحلي أيضاً: {resp_local}"
                    is_error = True

        # 3. المسار العادي
        else:
            success, resp = AIConnector.send_request(
                termux_ip, 
                DEFAULT_FAST_MODEL, 
                prompt, 
                timeout=60
            )
            if success:
                response_text = resp
            else:
                response_text = f"❌ خطأ: {resp}"
                is_error = True

        remove_typing(loading_control)
        add_chat_bubble(response_text, "bot", is_error)

    def send_message_click(e):
        prompt = input_field.value
        if not prompt: return
        
        input_field.value = ""
        add_chat_bubble(prompt, "user")
        
        loading = show_typing()
        
        l_ip = laptop_ip_input.value
        t_ip = termux_ip_input.value
        page.client_storage.set("laptop_ip", l_ip)
        page.client_storage.set("termux_ip", t_ip)

        t = threading.Thread(
            target=process_request_background,
            args=(prompt, l_ip, t_ip, loading),
            daemon=True
        )
        t.start()
        input_field.focus()

    # --- تخطيط الصفحة (Layout) ---
    def open_settings_dialog():
        dlg = ft.AlertDialog(
            title=ft.Text("إعدادات الشبكة"),
            content=ft.Column([
                ft.Text("عنوان سيرفر اللابتوب:", size=12),
                laptop_ip_input,
                ft.Divider(),
                ft.Text("عنوان Termux (اتركه 127.0.0.1 للتجربة محلياً):", size=12),
                termux_ip_input,
            ], height=200, width=300),
            actions=[
                ft.TextButton("حفظ وإغلاق", on_click=lambda e: page.close_dialog())
            ],
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    # شريط علوي (AppBar)
    page.appbar = ft.AppBar(
        # التصحيح هنا: استخدام ft.Icons و ft.Colors (أحرف كبيرة)
        leading=ft.Icon(ft.Icons.SMART_TOY_OUTLINED, color=ft.Colors.CYAN_400),
        leading_width=40,
        title=ft.Text("المساعد الذكي الهجين", weight="bold"),
        center_title=False,
        bgcolor="#1f1f1f",
        actions=[
            ft.IconButton(ft.Icons.SETTINGS, on_click=lambda e: open_settings_dialog())
        ],
    )

    page.add(
        ft.Column(
            [
                chat_list,
                ft.Container(
                    content=ft.Row([
                        input_field,
                        ft.FloatingActionButton(icon=ft.Icons.SEND, on_click=send_message_click, bgcolor="#2196F3")
                    ]),
                    padding=10,
                    bgcolor="#161616"
                )
            ],
            expand=True
        )
    )

ft.app(target=main)