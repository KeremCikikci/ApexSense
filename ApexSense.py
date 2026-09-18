import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import time
import statistics
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator
import json
import os
import sys

def get_writable_path(filename=""):
    base_path = os.path.join(os.environ.get('APPDATA'), "ApexSense")
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    return os.path.join(base_path, filename)

def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

ctk.set_appearance_mode("Light")  
ctk.set_default_color_theme("blue")

class BoyOlcumSistemi(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("ApexSense")
        
        try:
            ikon_yolu = resource_path("ApexSense.png")
            ikon = tk.PhotoImage(file=ikon_yolu)
            self.iconphoto(True, ikon)
        except Exception as e:
            print(f"İkon yüklenemedi: {e}")
            
        self.geometry("1200x800")
        self.minsize(900, 600)
        
        self.ser = None
        self.ayarlar_dosyasi = get_writable_path("settings.json")
        self.veri_klasoru = get_writable_path("measurements")
        
        os.makedirs(self.veri_klasoru, exist_ok=True)
        
        self.ayarlari_yukle()
        self.verileri_yukle()
        
        son_set = self.ayar.get("son_set", list(self.setler.keys())[0])
        if son_set not in self.setler:
            son_set = list(self.setler.keys())[0]
        self.aktif_set = tk.StringVar(value=son_set)
        
        self.sabit_baslangic = 0
        self.son_boy = 0
        self.kayit_tamam = False
        self.aktif_olcum_verileri = []
        self.son_veri_zamani = 0
        self.son_hb_zamani = 0 
        
        self.kisi_altinda = False
        self.kisi_ayrilma_baslangic = 0
        self.durum = "hazir" 

        self.arayuz_olustur()
        self.port_baglan()
        self.after(100, self.seri_dinle)
        self.after(50, self.led_kontrol)

    def ayarlari_yukle(self):
        varsayilan = {
            "com_port": "", 
            "sensor_yuksekligi": 200, 
            "min_boy": 130, 
            "bekleme_suresi": 3.0, 
            "ayrilma_suresi": 1.0, 
            "son_set": "Set 1",
            "buzzer_aktif": True
        }
        if os.path.exists(self.ayarlar_dosyasi):
            with open(self.ayarlar_dosyasi, "r") as f:
                self.ayar = json.load(f)
                degisti = False
                if "ayrilma_suresi" not in self.ayar:
                    self.ayar["ayrilma_suresi"] = 1.0
                    degisti = True
                if "buzzer_aktif" not in self.ayar:
                    self.ayar["buzzer_aktif"] = True
                    degisti = True
                
                if degisti:
                    self.ayarlari_kaydet()
        else:
            self.ayar = varsayilan
            self.ayarlari_kaydet()

    def ayarlari_kaydet(self):
        with open(self.ayarlar_dosyasi, "w") as f:
            json.dump(self.ayar, f)

    def dosya_yolu(self, set_adi):
        return os.path.join(self.veri_klasoru, f"{set_adi}.json")

    def verileri_yukle(self):
        self.setler = {}
        for dosya in os.listdir(self.veri_klasoru):
            if dosya.endswith(".json"):
                ad = dosya[:-5]
                with open(os.path.join(self.veri_klasoru, dosya), "r") as f:
                    self.setler[ad] = json.load(f)
        if not self.setler:
            self.setler["Set 1"] = []
            self.seti_kaydet("Set 1")

    def seti_kaydet(self, set_adi):
        with open(self.dosya_yolu(set_adi), "w") as f:
            json.dump(self.setler[set_adi], f)

    def port_baglan(self):
        if self.ayar["com_port"]:
            try:
                if self.ser and self.ser.is_open: 
                    self.ser.close()
                self.ser = serial.Serial(self.ayar["com_port"], 9600, timeout=0.5)
                self.ser.setDTR(False)
                time.sleep(1)
                self.ser.flushInput()
                self.ser.setDTR(True)
                time.sleep(1.5)

                dogrulandi = False
                for _ in range(10):
                    if self.ser.in_waiting > 0:
                        veri = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if veri.isdigit():
                            mesafe = int(veri)
                            if 0 <= mesafe <= 400:
                                dogrulandi = True
                                break
                    time.sleep(0.1)

                if dogrulandi:
                    self.ser.timeout = 0.1
                    print(f"Bağlantı Başarılı: {self.ayar['com_port']}")
                    
                    ses_seviyesi = 9 if self.ayar.get("buzzer_aktif", True) else 0
                    self.ser.write(f"V{ses_seviyesi}\n".encode())
                    self.ser.flush() 
                    print(f"Başlangıç ses seviyesi Arduino'ya iletildi: V{ses_seviyesi}")
                    
                else:
                    self.ser.close()
                    self.ser = None
                    print(f"Bağlantı Başarısız: {self.ayar['com_port']}")
                    
            except Exception as e:
                self.ser = None
                print(f"Bağlantı Başarısız: {self.ayar['com_port']} Hata: {e}")
        else:
            print("Bağlantı Bekleniyor.")

    def arayuz_olustur(self):
        self.ust_panel = ctk.CTkFrame(self, height=60, corner_radius=15, fg_color="white")
        self.ust_panel.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkButton(self.ust_panel, text="⚙ Ayarlar", font=("Segoe UI", 12, "bold"), width=100, command=self.ayarlar_penceresi).pack(side="left", padx=10, pady=15)
        
        self.set_combo = ctk.CTkComboBox(self.ust_panel, variable=self.aktif_set, values=list(self.setler.keys()), font=("Segoe UI", 12), command=self.guncelle)
        self.set_combo.pack(side="left", padx=5)
        
        ctk.CTkButton(self.ust_panel, text="➕ Yeni Set", font=("Segoe UI", 12), width=90, fg_color="#2ecc71", hover_color="#27ae60", command=self.yeni_set).pack(side="left", padx=5)
        ctk.CTkButton(self.ust_panel, text="✎ Ad Değiştir", font=("Segoe UI", 12), width=100, fg_color="#f39c12", hover_color="#e67e22", command=self.set_ad_degistir).pack(side="left", padx=5)
        ctk.CTkButton(self.ust_panel, text="🗑 Sil", font=("Segoe UI", 12), width=60, fg_color="#e74c3c", hover_color="#c0392b", command=self.set_sil).pack(side="left", padx=5)

        self.lbl_canli_veri = ctk.CTkLabel(self.ust_panel, text="", font=("Segoe UI", 18, "bold"), text_color="black")
        self.lbl_canli_veri.pack(side="right", padx=20)
        
        led_frame = ctk.CTkFrame(self.ust_panel, fg_color="transparent")
        led_frame.pack(side="right", padx=10, pady=15)
        
        self.led_baglanti = ctk.CTkFrame(led_frame, width=18, height=18, corner_radius=9, fg_color="#bdc3c7")
        self.led_baglanti.pack(side="left", padx=4)
        self.led_durum = ctk.CTkFrame(led_frame, width=18, height=18, corner_radius=9, fg_color="#bdc3c7")
        self.led_durum.pack(side="left", padx=4)

        ana_govde = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        ana_govde.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.sol_panel = ctk.CTkFrame(ana_govde, width=320, corner_radius=15, fg_color="white")
        ana_govde.add(self.sol_panel, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        
        style.configure("Treeview", background="white", foreground="black", rowheight=50, fieldbackground="white", borderwidth=0, font=("Segoe UI", 28))
        style.map('Treeview', background=[('selected', '#3498db')], foreground=[('selected', 'white')])
        style.configure("Treeview.Heading", background="#f8f9fa", foreground="black", relief="flat", font=("Segoe UI", 28, "bold"))
        style.map("Treeview.Heading", background=[('active', '#e9ecef')])

        tree_scroll = ttk.Scrollbar(self.sol_panel)
        tree_scroll.pack(side="right", fill="y", pady=10)

        self.tree = ttk.Treeview(self.sol_panel, columns=("Boy"), show="headings", height=15, yscrollcommand=tree_scroll.set)
        self.tree.heading("Boy", text="Ölçümler (cm)")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        tree_scroll.config(command=self.tree.yview)
        
        self.tree.bind("<<TreeviewSelect>>", self.veri_secildi)
        self.tree.bind("<ButtonPress-1>", self.agac_tiklandi_ve_surukle_basla)
        self.tree.bind("<ButtonRelease-1>", self.surukle_birak)
        self.tree.bind("<Double-1>", self.veri_duzenle_cift_tik)
        self.tree.bind("<Button-3>", self.sag_tik_menusu)

        self.sag_menu = tk.Menu(self, tearoff=0, font=("Segoe UI", 12))
        self.sag_menu.add_command(label="Değiştir", command=self.veri_duzenle)
        self.sag_menu.add_separator()
        self.sag_menu.add_command(label="Sil", command=self.veri_sil)

        ekle_frame = ctk.CTkFrame(self.sol_panel, fg_color="transparent")
        ekle_frame.pack(fill="x", padx=10, pady=5)
        self.ent_manuel = ctk.CTkEntry(ekle_frame, width=120, placeholder_text="Manuel (cm)", font=("Segoe UI", 12))
        self.ent_manuel.pack(side="left", padx=5)
        self.ent_manuel.bind("<Return>", lambda e: self.manuel_ekle())
        ctk.CTkButton(ekle_frame, text="Ekle", width=70, font=("Segoe UI", 12, "bold"), command=self.manuel_ekle).pack(side="left", padx=5)

        ist_kart = ctk.CTkFrame(self.sol_panel, corner_radius=10, fg_color="#f8f9fa")
        ist_kart.pack(fill="x", padx=10, pady=10)
        
        self.lbl_istatistik = ctk.CTkLabel(ist_kart, text="Veri Bekleniyor...", justify="left", font=("Segoe UI", 15), text_color="#2c3e50")
        self.lbl_istatistik.pack(padx=10, pady=10, fill="x")

        self.sag_panel = ctk.CTkFrame(ana_govde, corner_radius=15, fg_color="white")
        ana_govde.add(self.sag_panel, weight=3)
        
        self.fig = Figure(figsize=(7, 6), dpi=100, facecolor='white')
        self.ax1 = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212)
        self.fig.subplots_adjust(left=0.1, right=0.95, bottom=0.1, top=0.9, hspace=0.4)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.sag_panel)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.mpl_connect('button_press_event', self.grafik_tiklandi)

        self.dev_ekran = ctk.CTkFrame(self.sag_panel, corner_radius=15, fg_color="white")
        self.lbl_dev_boy = ctk.CTkLabel(self.dev_ekran, text="", font=("Segoe UI", 100, "bold"), text_color="black")
        self.lbl_dev_boy.pack(expand=True)
        self.lbl_geri_sayim = ctk.CTkLabel(self.dev_ekran, text="", font=("Segoe UI", 45, "bold"), text_color="#e74c3c")
        self.lbl_geri_sayim.pack(pady=(0, 60))
        
        self.guncelle()

    def led_kontrol(self):
        su_an = time.time()
        
        if self.ser and self.ser.is_open:
            self.led_baglanti.configure(fg_color="#e74c3c")
            
            try:
                if su_an - self.son_hb_zamani > 0.5:
                    self.ser.write(b'H') 
                    
                    if self.durum == "hazir":
                        self.ser.write(b'1')
                    elif self.durum == "olcum":
                        self.ser.write(b'2')
                    elif self.durum == "tamam":
                        self.ser.write(b'3')
                        
                    self.son_hb_zamani = su_an
            except Exception:
                pass 
                
        else:
            if int(su_an * 2) % 2 == 0:
                self.led_baglanti.configure(fg_color="#e74c3c")
            else:
                self.led_baglanti.configure(fg_color="#bdc3c7")

        if self.durum == "hazir":
            if int(su_an * 2) % 2 == 0:
                self.led_durum.configure(fg_color="#f1c40f") 
            else:
                self.led_durum.configure(fg_color="#bdc3c7")
        elif self.durum == "olcum":
            gecen = su_an - self.sabit_baslangic
            hiz = 2 + (gecen / self.ayar["bekleme_suresi"]) * 10
            if int(su_an * hiz) % 2 == 0:
                self.led_durum.configure(fg_color="#e74c3c") 
            else:
                self.led_durum.configure(fg_color="#bdc3c7")
        elif self.durum == "tamam":
            self.led_durum.configure(fg_color="#2ecc71")

        self.after(50, self.led_kontrol)

    def ayarlar_penceresi(self):
        if hasattr(self, 'pencere_ayarlar') and self.pencere_ayarlar.winfo_exists():
            self.pencere_ayarlar.lift()
            return

        self.pencere_ayarlar = ctk.CTkToplevel(self)
        self.pencere_ayarlar.title("Ayarlar")
        self.pencere_ayarlar.geometry("450x380") 
        self.pencere_ayarlar.attributes("-topmost", True)
        
        p = ctk.CTkFrame(self.pencere_ayarlar, corner_radius=10, fg_color="white")
        p.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(p, text="COM Port:", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        portlar = [prt.device for prt in serial.tools.list_ports.comports()]
        port_secici = ctk.CTkComboBox(p, values=portlar if portlar else [""])
        port_secici.set(self.ayar["com_port"])
        port_secici.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(p, text="Sensör Yük. (cm):", font=("Segoe UI", 12, "bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        ent_sens = ctk.CTkEntry(p)
        ent_sens.insert(0, str(self.ayar["sensor_yuksekligi"]))
        ent_sens.grid(row=1, column=1, padx=10, pady=10)

        ctk.CTkLabel(p, text="Min Boy (cm):", font=("Segoe UI", 12, "bold")).grid(row=2, column=0, padx=10, pady=10, sticky="w")
        ent_min = ctk.CTkEntry(p)
        ent_min.insert(0, str(self.ayar["min_boy"]))
        ent_min.grid(row=2, column=1, padx=10, pady=10)

        ctk.CTkLabel(p, text="Kayıt Süresi (sn):", font=("Segoe UI", 12, "bold")).grid(row=3, column=0, padx=10, pady=10, sticky="w")
        ent_sure = ctk.CTkEntry(p)
        ent_sure.insert(0, str(self.ayar["bekleme_suresi"]))
        ent_sure.grid(row=3, column=1, padx=10, pady=10)
        
        ctk.CTkLabel(p, text="Ayrılma Süresi (sn):", font=("Segoe UI", 12, "bold")).grid(row=4, column=0, padx=10, pady=10, sticky="w")
        ent_ayrilma = ctk.CTkEntry(p)
        ent_ayrilma.insert(0, str(self.ayar.get("ayrilma_suresi", 1.0)))
        ent_ayrilma.grid(row=4, column=1, padx=10, pady=10)

        ctk.CTkLabel(p, text="Buzzer:", font=("Segoe UI", 12, "bold")).grid(row=5, column=0, padx=10, pady=10, sticky="w")
        
        buzzer_var = ctk.BooleanVar(value=self.ayar.get("buzzer_aktif", True))
        
        def buzzer_degisti():
            ses_seviyesi = 9 if buzzer_var.get() else 0
            if self.ser and self.ser.is_open:
                try:
                    self.ser.write(f"V{ses_seviyesi}\n".encode())
                except Exception:
                    pass

        cb_buzzer = ctk.CTkCheckBox(p, text="Aktif", variable=buzzer_var, command=buzzer_degisti)
        cb_buzzer.grid(row=5, column=1, padx=10, pady=10, sticky="w")

        def kaydet():
            self.ayar["com_port"] = port_secici.get()
            self.ayar["sensor_yuksekligi"] = int(ent_sens.get())
            self.ayar["min_boy"] = int(ent_min.get())
            self.ayar["bekleme_suresi"] = float(ent_sure.get())
            self.ayar["ayrilma_suresi"] = float(ent_ayrilma.get())
            self.ayar["buzzer_aktif"] = buzzer_var.get()
            self.ayarlari_kaydet()
            self.port_baglan()
            self.pencere_ayarlar.destroy()
            
        ctk.CTkButton(p, text="Kaydet", font=("Segoe UI", 12, "bold"), command=kaydet).grid(row=6, columnspan=3, pady=15)

    def yeni_set(self):
        dialog = ctk.CTkInputDialog(text="Yeni Set Adı Girin:", title="Set Oluştur")
        isim = dialog.get_input()
        if isim and isim not in self.setler:
            self.setler[isim] = []
            self.seti_kaydet(isim)
            self.set_combo.configure(values=list(self.setler.keys()))
            self.aktif_set.set(isim)
            self.guncelle()

    def set_ad_degistir(self):
        eski_isim = self.aktif_set.get()
        dialog = ctk.CTkInputDialog(text="Yeni Set Adı:", title="Ad Değiştir")
        yeni_isim = dialog.get_input()
        if yeni_isim and yeni_isim != eski_isim and yeni_isim not in self.setler:
            self.setler[yeni_isim] = self.setler.pop(eski_isim)
            os.rename(self.dosya_yolu(eski_isim), self.dosya_yolu(yeni_isim))
            self.set_combo.configure(values=list(self.setler.keys()))
            self.aktif_set.set(yeni_isim)

    def set_sil(self):
        isim = self.aktif_set.get()
        cevap = messagebox.askyesno("Onay", f"'{isim}' setini tamamen silmek istiyor musunuz?")
        if cevap:
            del self.setler[isim]
            os.remove(self.dosya_yolu(isim))
            if not self.setler:
                self.setler["Set 1"] = []
                self.seti_kaydet("Set 1")
            self.set_combo.configure(values=list(self.setler.keys()))
            self.aktif_set.set(list(self.setler.keys())[0])
            self.guncelle()

    def manuel_ekle(self):
        veri = self.ent_manuel.get()
        if veri.isdigit():
            self.setler[self.aktif_set.get()].append(int(veri))
            self.seti_kaydet(self.aktif_set.get())
            self.ent_manuel.delete(0, tk.END)
            self.guncelle()

    def sag_tik_menusu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.sag_menu.tk_popup(event.x_root, event.y_root)

    def veri_sil(self):
        secili = self.tree.selection()
        if secili:
            idx = self.tree.index(secili[0])
            del self.setler[self.aktif_set.get()][idx]
            self.seti_kaydet(self.aktif_set.get())
            self.guncelle()

    def veri_duzenle(self):
        secili = self.tree.selection()
        if secili:
            idx = self.tree.index(secili[0])
            eski = self.setler[self.aktif_set.get()][idx]
            dialog = ctk.CTkInputDialog(text=f"Yeni değeri girin (Eski: {eski}):", title="Düzenle")
            yeni_str = dialog.get_input()
            if yeni_str and yeni_str.isdigit():
                self.setler[self.aktif_set.get()][idx] = int(yeni_str)
                self.seti_kaydet(self.aktif_set.get())
                self.guncelle()

    def veri_duzenle_cift_tik(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.veri_duzenle()

    def agac_tiklandi_ve_surukle_basla(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            if self.tree.selection():
                self.tree.selection_remove(self.tree.selection())
                self.grafikleri_ciz()
        else:
            self._suruklenen_item = item

    def surukle_birak(self, event):
        if hasattr(self, '_suruklenen_item') and self._suruklenen_item:
            hedef_item = self.tree.identify_row(event.y)
            if hedef_item and hedef_item != self._suruklenen_item:
                eski_idx = self.tree.index(self._suruklenen_item)
                yeni_idx = self.tree.index(hedef_item)
                
                set_adi = self.aktif_set.get()
                veri = self.setler[set_adi].pop(eski_idx)
                self.setler[set_adi].insert(yeni_idx, veri)
                
                self.seti_kaydet(set_adi)
                self.guncelle()
            self._suruklenen_item = None

    def veri_secildi(self, event):
        secili = self.tree.selection()
        if secili:
            self.grafikleri_ciz(self.tree.index(secili[0]))

    def grafik_tiklandi(self, event):
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
            self.grafikleri_ciz()

    def grafikleri_ciz(self, secili_idx=None):
        veriler = self.setler.get(self.aktif_set.get(), [])
        self.ax1.clear()
        self.ax2.clear()

        if len(veriler) > 0:
            self.ax1.spines['top'].set_visible(False)
            self.ax1.spines['right'].set_visible(False)
            self.ax2.spines['top'].set_visible(False)
            self.ax2.spines['right'].set_visible(False)
            
            self.ax1.grid(color='#e0e0e0', linestyle='--', linewidth=0.8, alpha=0.7, axis='y')
            self.ax2.grid(color='#e0e0e0', linestyle='--', linewidth=0.8, alpha=0.7, axis='y')

            self.ax1.plot(range(1, len(veriler)+1), veriler, color='#2ecc71', marker='o', linewidth=3, markersize=9)
            
            if secili_idx is not None:
                self.ax1.plot(secili_idx + 1, veriler[secili_idx], color='#e74c3c', marker='o', markersize=15)
            
            self.ax1.set_title("Nokta Grafiği", fontdict={'fontsize': 28, 'fontweight': 'bold', 'color': '#2c3e50'})
            self.ax1.set_xlabel("Ölçüm Sırası", fontdict={'fontsize': 20})
            self.ax1.set_ylabel("Boy Uzunluğu (cm)", fontdict={'fontsize': 20})
            self.ax1.xaxis.set_major_locator(MaxNLocator(integer=True))
            self.ax1.tick_params(axis='both', which='major', labelsize=18)

        n, bins, patches = self.ax2.hist(veriler, bins=len(set(veriler))+1, color='#3498db', edgecolor='white', rwidth=0.85)

        if secili_idx is not None:
            secili_boy = veriler[secili_idx]
            for i in range(len(bins)-1):
                if bins[i] <= secili_boy <= bins[i+1]:
                    patches[i].set_facecolor('#e74c3c') 
                    break

        self.ax2.set_title("Frekans Dağılımı", fontdict={'fontsize': 28, 'fontweight': 'bold', 'color': '#2c3e50'})
        self.ax2.set_xlabel("Boy Uzunluğu (cm)", fontdict={'fontsize': 20})
        self.ax2.set_ylabel("Tekrar Frekansı (Adet)", fontdict={'fontsize': 20})

        self.ax2.yaxis.set_major_locator(MaxNLocator(integer=True))
        self.ax2.tick_params(axis='both', which='major', labelsize=18)

        self.ax2.yaxis.grid(True, linestyle='--', alpha=0.3)
        self.ax2.set_axisbelow(True)
        
        self.canvas.draw()

    def guncelle(self, event=None):
        self.ayar["son_set"] = self.aktif_set.get()
        self.ayarlari_kaydet()

        veriler = self.setler.get(self.aktif_set.get(), [])
        
        for row in self.tree.get_children(): self.tree.delete(row)
        for v in veriler: self.tree.insert("", "end", values=(v,))
        ist_metin = "Veri Bekleniyor..."
        if len(veriler) > 0:
            ort = statistics.mean(veriler)
            mi, ma = min(veriler), max(veriler)
            ranj = ma - mi
            med = statistics.median(veriler)
            
            frekanslar = {x: veriler.count(x) for x in set(veriler)}
            mod = max(frekanslar, key=frekanslar.get)
            
            son_veri = veriler[-1]
            kucuk_esitler = sum(1 for v in veriler if v <= son_veri)
            yuzde = (kucuk_esitler / len(veriler)) * 100
            
            ist_metin = (f"📈 Ortalama:  {ort:.1f}\n"
                         f"⬇ Min: {mi}   ⬆ Max: {ma}\n"
                         f"↔ Ranj: {ranj}\n"
                         f"🎯 Medyan: {med}\n"
                         f"🔥 Mod: {mod}\n"
                         f"📊 Son Ölçüm Yüzdelik Dilim:  %{yuzde:.1f}")
            self.lbl_istatistik.configure(text=ist_metin, justify="left", anchor="w")
        else:
            self.lbl_istatistik.configure(text=ist_metin, justify="left", anchor="w")
            
        self.grafikleri_ciz()

    def seri_dinle(self):
        if self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    veri = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if veri:
                        self.son_veri_zamani = time.time()
                        
                        if veri.isdigit():
                            mesafe = int(veri)
                            self.lbl_canli_veri.configure(text=str(mesafe))
                            boy = self.ayar["sensor_yuksekligi"] - mesafe
                            
                            if boy > self.ayar["min_boy"]:
                                self.kisi_altinda = True
                                self.kisi_ayrilma_baslangic = 0
                                
                                self.dev_ekran.place(relx=0, rely=0, relwidth=1, relheight=1)
                                
                                if not self.kayit_tamam:
                                    self.durum = "olcum"
                                    self.lbl_dev_boy.configure(text=f"{boy} cm")
                                    
                                    if abs(boy - self.son_boy) <= 1:
                                        self.aktif_olcum_verileri.append(boy)
                                        gecen = time.time() - self.sabit_baslangic
                                        kalan = self.ayar["bekleme_suresi"] - gecen
                                        
                                        if kalan > 0:
                                            self.lbl_geri_sayim.configure(text=f"Kayıt: {kalan:.1f} sn", text_color="#e74c3c")
                                        else:
                                            self.lbl_geri_sayim.configure(text="Alandan ayrılınız", text_color="#2ecc71")
                                            self.durum = "tamam"
                                            
                                            ortalama_boy = int(round(statistics.mean(self.aktif_olcum_verileri)))
                                            self.lbl_dev_boy.configure(text=f"{ortalama_boy} cm")
                                            
                                            self.setler[self.aktif_set.get()].append(ortalama_boy)
                                            self.seti_kaydet(self.aktif_set.get())
                                            self.guncelle()
                                            self.kayit_tamam = True
                                    else:
                                        self.son_boy = boy
                                        self.sabit_baslangic = time.time()
                                        self.aktif_olcum_verileri = [boy]
                                        self.lbl_geri_sayim.configure(text="Sabit durun...", text_color="#e74c3c")
                            else:
                                if self.kisi_altinda:
                                    if self.kisi_ayrilma_baslangic == 0:
                                        self.kisi_ayrilma_baslangic = time.time()
                                    elif time.time() - self.kisi_ayrilma_baslangic >= self.ayar.get("ayrilma_suresi", 1.0):
                                        self.dev_ekran.place_forget()
                                        self.kayit_tamam = False
                                        self.son_boy = 0
                                        self.aktif_olcum_verileri = []
                                        self.kisi_altinda = False
                                        self.kisi_ayrilma_baslangic = 0
                                        self.durum = "hazir"
                else:
                    if time.time() - self.son_veri_zamani > 1.5:
                        if not self.kisi_altinda:
                            self.lbl_canli_veri.configure(text="")
            except Exception as e:
                pass
        else:
            self.lbl_canli_veri.configure(text="")
            
        self.after(50, self.seri_dinle)

if __name__ == "__main__":
    app = BoyOlcumSistemi()
    app.mainloop()