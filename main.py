import flet as ft
import requests
import threading
import time
from datetime import datetime
import logging

# --- إعداد السجلات ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- الثوابت الافتراضية ---
DEFAULT_LAPTOP_IP = "192.168.1.6"
DEFAULT_TERMUX_IP = "127.0.0.1"
DEFAULT_FAST_MODEL = "qwen:0.5b"
DEFAULT_SMART_MODEL = "gemma:2b"
DEFAULT_THINKER_REMOTE = "qwen2.5:4b"

# --- طبقة الاتصال (Network Layer) ---
class AIConnector:
    @staticmethod
    def ping_server(url_base):
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            # مهلة قصيرة جداً للفحص الدوري
            requests.get(f"{url_base}:11434", timeout=1)
            return True
        except:
            return False

    @staticmethod
    def send_request(url_base, model, prompt, timeout):
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            url = f"{url_base}:11434/api/generate"
            payload = {
                "model": model, 
                "prompt": prompt, 
                "stream": False, 
                "options": {"num_ctx": 4096}
            }
            logging.info(f"Connecting to {url}...")
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return True, response.json().get("response", "")
        except requests.exceptions.Timeout:
            return False, "⚠️ انتهت مهلة التفكير (Timeout)."
        except requests.exceptions.ConnectionError:
            return False, f"❌ تعذر الاتصال بـ {url_base}. تأكد أن 'ollama serve' يعمل."
        except Exception as e:
            return False, f"Error: {str(e)}"

def main(page: ft.Page):
    # --- نظام الإقلاع الآمن (Safe Boot) ---
    try:
        # 1. إعدادات الصفحة الأساسية
        page.title = "AI Nexus V3"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0e0e0e"
        page.padding = 0
        
        # 2. رسم شاشة تحميل فورية (لمنع الشاشة السوداء)
        loading_screen = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=ft.Colors.BLUE_400),
                ft.Text("جاري تهيئة النظام...", color=ft.Colors.GREY_400)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
            bgcolor="#0e0e0e"
        )
        page.add(loading_screen)
        page.update()
        
        # مهلة قصيرة لضمان رسم الواجهة
        time.sleep(0.5)

        # 3. تحميل البيانات (داخل Try لتجنب الانهيار)
        try:
            l_ip = page.client_storage.get("laptop_ip") or DEFAULT_LAPTOP_IP
            t_ip = page.client_storage.get("termux_ip") or DEFAULT_TERMUX_IP
            f_mod = page.client_storage.get("fast_model") or DEFAULT_FAST_MODEL
            s_mod = page.client_storage.get("smart_model") or DEFAULT_SMART_MODEL
            r_mod = page.client_storage.get("remote_model") or DEFAULT_THINKER_REMOTE
        except Exception as e:
            logging.error(f"Storage Error: {e}")
            l_ip, t_ip, f_mod, s_mod, r_mod = DEFAULT_LAPTOP_IP, DEFAULT_TERMUX_IP, DEFAULT_FAST_MODEL, DEFAULT_SMART_MODEL, DEFAULT_THINKER_REMOTE

        # --- تعريف عناصر الواجهة ---
        
        # مؤشرات الحالة
        termux_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.GREY_800, size=12, tooltip="Termux Status")
        laptop_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.GREY_800, size=12, tooltip="Laptop Status")

        # حقول الإدخال للإعدادات
        laptop_input = ft.TextField(label="Laptop IP", value=l_ip, border_color=ft.Colors.BLUE_700)
        termux_input = ft.TextField(label="Termux IP", value=t_ip, border_color=ft.Colors.GREEN_700)
        
        fast_input = ft.TextField(label="Fast Model", value=f_mod, text_size=12)
        smart_input = ft.TextField(label="Local Thinker", value=s_mod, text_size=12)
        remote_input = ft.TextField(label="Remote Thinker", value=r_mod, text_size=12)

        # --- الخيط الخلفي لمراقبة الشبكة ---
        def health_loop():
            while True:
                try:
                    # فحص Termux
                    if AIConnector.ping_server(termux_input.value):
                        termux_led.color = ft.Colors.GREEN_ACCENT_400
                    else:
                        termux_led.color = ft.Colors.RED_900
                    
                    # فحص Laptop
                    if AIConnector.ping_server(laptop_input.value):
                        laptop_led.color = ft.Colors.BLUE_ACCENT_400
                    else:
                        laptop_led.color = ft.Colors.RED_900
                    
                    page.update()
                except:
                    pass # تجاهل الأخطاء في الخيط الخلفي لمنع الإغلاق
                time.sleep(8)

        # --- منطق المحادثة ---
        chat_list = ft.ListView(expand=True, spacing=10, padding=15, auto_scroll=True)
        input_field = ft.TextField(hint_text="تحدث هنا...", border_radius=25, bgcolor=ft.Colors.GREY_900, border_color=ft.Colors.TRANSPARENT, expand=True)

        def add_bubble(text, sender="user", is_error=False):
            align = ft.MainAxisAlignment.END if sender == "user" else ft.MainAxisAlignment.START
            if sender == "user": bg = ft.Colors.BLUE_900
            elif is_error: bg = ft.Colors.RED_900
            else: bg = ft.Colors.GREY_800
            
            bubble = ft.Container(
                content=ft.Markdown(text, selectable=True),
                padding=12, border_radius=12, bgcolor=bg,
                width=300 if len(text) > 50 else None
            )
            chat_list.controls.append(ft.Row([bubble], alignment=align))
            page.update()

        def process_ai(prompt):
            # إظهار مؤشر كتابة بسيط
            loading_bubble = ft.Row([ft.ProgressRing(width=15, height=15), ft.Text(" جاري التفكير...")], alignment=ft.MainAxisAlignment.START)
            chat_list.controls.append(loading_bubble)
            page.update()

            # جلب القيم الحالية
            curr_l_ip = laptop_input.value
            curr_t_ip = termux_input.value
            
            response = ""
            error_flag = False
            
            # 1. المسار السريع
            if any(x in prompt for x in ["ساعة", "تاريخ", "وقت"]):
                response = f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # 2. مسار التفكير (المفكر)
            elif any(x in prompt for x in ["فكر", "بعمق", "خطط", "تحليل"]):
                success, resp = AIConnector.send_request(
                    curr_l_ip, remote_input.value, 
                    f"أنت مهندس خبير. فكر بعمق وتفصيل. السؤال: {prompt}", 300
                )
                if success:
                    response = f"🧠 **(المفكر العملاق):**\n\n{resp}"
                else:
                    response = f"⚠️ **فشل اللابتوب، أحول للمحلي...**\n\n"
                    s2, r2 = AIConnector.send_request(curr_t_ip, smart_input.value, f"فكر بعمق: {prompt}", 120)
                    if s2: response += f"📱 **(المفكر المحلي):**\n{r2}"
                    else: 
                        response += f"❌ فشل كلي: {r2}"
                        error_flag = True
            
            # 3. المسار العادي
            else:
                s, r = AIConnector.send_request(curr_t_ip, fast_input.value, prompt, 60)
                if s: response = r
                else: 
                    response = f"❌ خطأ: {r}"
                    error_flag = True

            # إزالة مؤشر التحميل وإضافة الرد
            chat_list.controls.remove(loading_bubble)
            add_bubble(response, "bot", error_flag)

        def send_click(e):
            if not input_field.value: return
            txt = input_field.value
            input_field.value = ""
            add_bubble(txt, "user")
            threading.Thread(target=process_ai, args=(txt,), daemon=True).start()
            input_field.focus()

        input_field.on_submit = send_click

        # --- نافذة الإعدادات ---
        def save_settings(e):
            page.client_storage.set("laptop_ip", laptop_input.value)
            page.client_storage.set("termux_ip", termux_input.value)
            page.client_storage.set("fast_model", fast_input.value)
            page.client_storage.set("smart_model", smart_input.value)
            page.client_storage.set("remote_model", remote_input.value)
            page.close(settings_dlg)
            page.snack_bar = ft.SnackBar(ft.Text("تم الحفظ!"), bgcolor="green")
            page.open(page.snack_bar)
            page.update()

        settings_content = ft.Column([
            ft.Text("الشبكة", weight="bold"), laptop_input, termux_input,
            ft.Divider(),
            ft.Text("النماذج", weight="bold"), fast_input, smart_input, remote_input
        ], height=350, scroll="auto")

        settings_dlg = ft.AlertDialog(
            title=ft.Text("الإعدادات"), content=settings_content,
            actions=[ft.ElevatedButton("حفظ", on_click=save_settings)]
        )

        # --- بناء الواجهة النهائية ---
        page.clean() # إزالة شاشة التحميل
        
        app_bar = ft.Row([
            ft.Text("AI Nexus", size=18, weight="bold"),
            ft.Container(expand=True),
            termux_led, ft.Container(width=10), laptop_led,
            ft.IconButton(ft.Icons.SETTINGS, on_click=lambda e: page.open(settings_dlg))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        page.add(
            ft.Container(app_bar, padding=10, bgcolor=ft.Colors.GREY_900),
            ft.Container(chat_list, expand=True),
            ft.Container(
                content=ft.Row([input_field, ft.IconButton(ft.Icons.SEND, on_click=send_click)]),
                padding=10, bgcolor=ft.Colors.GREY_900
            )
        )
        
        # تشغيل المراقب بعد اكتمال البناء
        threading.Thread(target=health_loop, daemon=True).start()

    except Exception as e:
        # شاشة الموت الأحمر (بدلاً من الأسود)
        page.clean()
        page.bgcolor = "#330000"
        page.add(
            ft.Column([
                ft.Icon(ft.Icons.ERROR_OUTLINE, color="red", size=50),
                ft.Text("فشل إقلاع التطبيق!", size=20, color="red", weight="bold"),
                ft.Text(f"الخطأ: {str(e)}", color="white", selectable=True)
            ], alignment=ft.MainAxisAlignment.CENTER)
        )
        page.update()

ft.app(target=main)