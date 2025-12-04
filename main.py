import flet as ft
import requests
import threading
import time
from datetime import datetime
import logging

# --- إعداد السجلات ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- الثوابت الافتراضية (تم ضبطها بدقة) ---
DEFAULT_LAPTOP_IP = "192.168.1.6"   # عنوان اللابتوب
DEFAULT_TERMUX_IP = "192.168.1.X"   # ⚠️ هام: ضع IP هاتفك هنا بدلاً من 127.0.0.1
DEFAULT_FAST_MODEL = "qwen:0.5b"    # نموذج السرعة والترحيب
DEFAULT_SMART_MODEL = "gemma:2b"    # نموذج الطوارئ الذكي (تيرمكس)
DEFAULT_THINKER_REMOTE = "qwen2.5:3b" # نموذج الوحش (اللابتوب)

class AIConnector:
    @staticmethod
    def ping_server(url_base):
        """فحص سريع هل السيرفر حي؟"""
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            requests.get(f"{url_base}:11434", timeout=1)
            return True
        except:
            return False

    @staticmethod
    def send_request(url_base, model, prompt, timeout):
        """إرسال الطلب مع معالجة ذكية للأخطاء"""
        try:
            if not url_base.startswith("http"): url_base = f"http://{url_base}"
            url = f"{url_base}:11434/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": 4096} # ذاكرة سياق جيدة
            }
            
            logging.info(f"Connecting to {url} -> Model: {model}")
            
            # زيادة المهلة للهاتف لأنه قد يكون بطيئاً في التحميل الأول
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return True, response.json().get("response", "")
            
        except requests.exceptions.HTTPError:
            if response.status_code == 500:
                return False, f"❌ خطأ داخلي: النموذج '{model}' غير موجود أو معطوب."
            return False, f"HTTP Error: {response.status_code}"
        except requests.exceptions.Timeout:
            return False, "⚠️ انتهت المهلة! (السيرفر يحتاج وقتاً أطول للتحميل)."
        except requests.exceptions.ConnectionError:
            return False, f"❌ تعذر الاتصال بـ {url_base} (تأكد من الـ IP)."
        except Exception as e:
            return False, f"Error: {str(e)}"

def main(page: ft.Page):
    try:
        # إعدادات الواجهة
        page.title = "AI Nexus V3.2 Pro"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0e0e0e"
        page.padding = 0
        
        # شاشة الترحيب
        loading_screen = ft.Container(
            content=ft.Column([
                ft.ProgressRing(color=ft.Colors.CYAN_400),
                ft.Text("جاري تهيئة البروتوكولات...", color=ft.Colors.GREY_400)
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center, expand=True, bgcolor="#0e0e0e"
        )
        page.add(loading_screen)
        page.update()
        time.sleep(0.5)

        # استرجاع البيانات المحفوظة
        try:
            l_ip = page.client_storage.get("laptop_ip") or DEFAULT_LAPTOP_IP
            t_ip = page.client_storage.get("termux_ip") or DEFAULT_TERMUX_IP
            f_mod = page.client_storage.get("fast_model") or DEFAULT_FAST_MODEL
            s_mod = page.client_storage.get("smart_model") or DEFAULT_SMART_MODEL
            r_mod = page.client_storage.get("remote_model") or DEFAULT_THINKER_REMOTE
        except:
            l_ip, t_ip, f_mod, s_mod, r_mod = DEFAULT_LAPTOP_IP, DEFAULT_TERMUX_IP, DEFAULT_FAST_MODEL, DEFAULT_SMART_MODEL, DEFAULT_THINKER_REMOTE

        # تعريف الحقول
        laptop_input = ft.TextField(label="Laptop IP", value=l_ip, border_color="blue")
        termux_input = ft.TextField(label="Phone IP (Not 127.0.0.1)", value=t_ip, border_color="green", hint_text="ضع عنوان هاتفك المحلي هنا")
        
        fast_input = ft.TextField(label="Fast Model (Greeting)", value=f_mod)
        smart_input = ft.TextField(label="Local Thinker (Backup)", value=s_mod)
        remote_input = ft.TextField(label="Remote Thinker (Primary)", value=r_mod)

        # مؤشرات الحالة
        termux_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.GREY_800, size=12)
        laptop_led = ft.Icon(name=ft.Icons.CIRCLE, color=ft.Colors.GREY_800, size=12)

        # مراقب الشبكة
        def health_loop():
            while True:
                try:
                    # فحص تيرمكس
                    if AIConnector.ping_server(termux_input.value):
                        termux_led.color = ft.Colors.GREEN_ACCENT_400
                        termux_led.tooltip = "تيرمكس متصل"
                    else:
                        termux_led.color = ft.Colors.RED_900
                        termux_led.tooltip = "تيرمكس غير متصل (تأكد من IP)"
                    
                    # فحص اللابتوب
                    if AIConnector.ping_server(laptop_input.value):
                        laptop_led.color = ft.Colors.BLUE_ACCENT_400
                        laptop_led.tooltip = "اللابتوب متصل"
                    else:
                        laptop_led.color = ft.Colors.RED_900
                        laptop_led.tooltip = "اللابتوب مفصول"
                    page.update()
                except: pass
                time.sleep(5)

        # قائمة المحادثة
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

        # --- العقل المدبر (Routing Logic) ---
        def process_ai(prompt):
            # مؤشر التفكير
            loading = ft.Row([ft.ProgressRing(width=15, height=15), ft.Text(" جاري المعالجة...")], alignment=ft.MainAxisAlignment.START)
            chat_list.controls.append(loading)
            page.update()

            # تنظيف النص
            clean_prompt = prompt.lower().strip().replace("ة", "ه").replace("أ", "ا")
            
            response = ""
            error_flag = False
            
            # جلب العناوين الحالية
            curr_l_ip = laptop_input.value
            curr_t_ip = termux_input.value

            # --- السيناريو 1: معلومات فورية (بدون ذكاء) ---
            if any(x in clean_prompt for x in ["ساعه", "تاريخ", "وقت"]):
                response = f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"

            # --- السيناريو 2: ترحيب بسيط (استخدام النموذج السريع محلياً) ---
            elif any(x in clean_prompt for x in ["مرحبا", "اهلا", "السلام عليكم", "هلا", "هاي"]):
                # نوجه الطلب لـ qwen:0.5b في تيرمكس
                s, r = AIConnector.send_request(curr_t_ip, fast_input.value, prompt, 30)
                if s: response = r
                else: 
                    response = f"❌ فشل النموذج السريع: {r}"
                    error_flag = True

            # --- السيناريو 3: تفكير وحل مشاكل (الأولوية للابتوب ثم التيرمكس) ---
            else:
                # خطوة 1: نحاول مع اللابتوب (الوحش)
                # نزيد المهلة لـ 5 دقائق للابتوب
                success_remote, resp_remote = AIConnector.send_request(
                    curr_l_ip, remote_input.value, 
                    f"أنت خبير استراتيجي. فكر بعمق في: {prompt}", 300
                )
                
                if success_remote:
                    response = f"🧠 **(اللابتوب):**\n\n{resp_remote}"
                else:
                    # خطوة 2: فشل اللابتوب؟ نذهب للتيرمكس الذكي (Backup)
                    response = f"⚠️ **اللابتوب غير متاح ({resp_remote})... جاري استدعاء المستشار المحلي.**\n\n"
                    
                    # مهلة 120 ثانية للهاتف
                    success_local, resp_local = AIConnector.send_request(
                        curr_t_ip, smart_input.value, 
                        f"فكر بعمق: {prompt}", 120
                    )
                    
                    if success_local:
                        response += f"📱 **(تيرمكس):**\n{resp_local}"
                    else:
                        response += f"❌ **فشل كلي:** {resp_local}"
                        error_flag = True

            chat_list.controls.remove(loading)
            add_bubble(response, "bot", error_flag)

        def send_click(e):
            if not input_field.value: return
            txt = input_field.value
            input_field.value = ""
            add_bubble(txt, "user")
            threading.Thread(target=process_ai, args=(txt,), daemon=True).start()
            input_field.focus()

        input_field.on_submit = send_click

        # حفظ الإعدادات
        def save_settings(e):
            page.client_storage.set("laptop_ip", laptop_input.value)
            page.client_storage.set("termux_ip", termux_input.value)
            page.client_storage.set("fast_model", fast_input.value)
            page.client_storage.set("smart_model", smart_input.value)
            page.client_storage.set("remote_model", remote_input.value)
            page.close(settings_dlg)
            page.update()

        # نافذة الإعدادات
        settings_content = ft.Column([
            ft.Text("إعدادات الشبكة", color="cyan"),
            laptop_input, 
            termux_input, 
            ft.Divider(), 
            ft.Text("تخصيص النماذج", color="cyan"), 
            fast_input, smart_input, remote_input
        ], height=400, scroll="auto")
        
        settings_dlg = ft.AlertDialog(title=ft.Text("الإعدادات"), content=settings_content, actions=[ft.ElevatedButton("حفظ", on_click=save_settings)])

        # تجميع الصفحة
        page.clean()
        app_bar = ft.Row([
            ft.Text("Hybrid AI V3.2", size=18, weight="bold"), 
            ft.Container(expand=True), 
            termux_led, ft.Container(width=10), laptop_led, 
            ft.IconButton(ft.Icons.SETTINGS, on_click=lambda e: page.open(settings_dlg))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        page.add(
            ft.Container(app_bar, padding=10, bgcolor=ft.Colors.GREY_900),
            ft.Container(chat_list, expand=True),
            ft.Container(content=ft.Row([input_field, ft.IconButton(ft.Icons.SEND, on_click=send_click)]), padding=10, bgcolor=ft.Colors.GREY_900)
        )
        
        threading.Thread(target=health_loop, daemon=True).start()

    except Exception as e:
        page.clean()
        page.add(ft.Text(f"Fatal Error: {e}", color="red"))

ft.app(target=main)