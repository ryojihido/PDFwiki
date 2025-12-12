import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import fitz  # PyMuPDF
import threading
import os
import sys
import json
import darkdetect
from pathlib import Path
from PIL import Image, ImageTk
import logging
import unicodedata
from collections import Counter

# Setup Logging
# Setup Logging - Console only (hidden in GUI mode)
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)

CONFIG_FILE = Path(__file__).parent / "config.json"

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

class PDFWikiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDFwiki v1.1.0")
        self.root.geometry("500x800") # Vertical ratio
        
        logging.info("App Started")
        
        # Icon Setup
        try:
            icon_path = resource_path("icon.ico")
            self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to load icon: {e}")
        
        # Configuration
        self.config = self.load_config()
        self.current_theme_setting = self.config.get("theme_mode", "System")
        self.current_theme_applied = None # Tracks actual applied theme (light/dark)
        
        # Data storage
        self.pdf_data = [] 
        self.current_pdf_path = None
        self.current_preview_image = None # Keep reference to prevent GC
        self.current_preview_page = None
        
        # Setup Theme
        self.apply_theme_mode(self.current_theme_setting)
        
        # GUI Setup
        self.setup_ui()
        
        # Start monitoring system theme if needed
        self.check_system_theme()

    def load_config(self):
        default_config = {"theme_mode": "System"}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return default_config
        return default_config

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Config save failed: {e}")

    def apply_theme_mode(self, mode):
        """
        mode: 'Light', 'Dark', or 'System'
        """
        self.current_theme_setting = mode
        self.config["theme_mode"] = mode
        self.save_config()
        
        target_theme = ""
        
        if mode == "System":
            # Detect system theme
            is_dark = darkdetect.isDark()
            target_theme = "darkly" if is_dark else "flatly"
        elif mode == "Dark":
            target_theme = "darkly"
        else: # Light
            target_theme = "flatly"
            
        # Only apply if changed
        if self.current_theme_applied != target_theme:
            style = ttk.Style(theme=target_theme)
            self.current_theme_applied = target_theme

    def check_system_theme(self):
        """Poll system theme changes if mode is System"""
        if self.current_theme_setting == "System":
            is_dark = darkdetect.isDark()
            expected_theme = "darkly" if is_dark else "flatly"
            if self.current_theme_applied != expected_theme:
                # Re-apply system theme to switch
                self.apply_theme_mode("System")
        
        # Check again in 2 seconds
        self.root.after(2000, self.check_system_theme)

    def set_theme_command(self, mode):
        logging.info(f"Theme switched to: {mode}")
        self.apply_theme_mode(mode)

    def setup_ui(self):
        # Menu Bar
        menubar = ttk.Menu(self.root)
        self.root.config(menu=menubar)
        
        settings_menu = ttk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="設定", menu=settings_menu)
        
        theme_menu = ttk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="テーマ", menu=theme_menu)
        theme_menu.add_radiobutton(label="Light", command=lambda: self.set_theme_command("Light"))
        theme_menu.add_radiobutton(label="Dark", command=lambda: self.set_theme_command("Dark"))
        theme_menu.add_radiobutton(label="System", command=lambda: self.set_theme_command("System"))
        
        # Tools Menu - Removed for release
        # tools_menu = ttk.Menu(menubar, tearoff=0)
        # menubar.add_cascade(label="ツール", menu=tools_menu)
        # tools_menu.add_command(label="デバッグログを開く", command=self.open_debug_log)
        self.paned_window = ttk.Panedwindow(self.root, orient=HORIZONTAL)
        self.paned_window.pack(fill=BOTH, expand=True)
        
        # Left Pane (Search & List)
        self.left_pane = ttk.Frame(self.paned_window)
        self.paned_window.add(self.left_pane, weight=1) 
        
        # Right Pane (Preview) - initially not added (hidden)
        self.right_pane = ttk.Frame(self.paned_window, padding=10, bootstyle="secondary")
        
        # --- Left Pane Contents ---
        top_frame = ttk.Frame(self.left_pane, padding=10)
        top_frame.pack(fill=X)
        
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.top_check = ttk.Checkbutton(
            top_frame, text="常に手前に表示", variable=self.always_on_top_var,
            bootstyle="round-toggle", command=self.toggle_topmost
        )
        self.top_check.pack(anchor=W)
        
        self.load_btn = ttk.Button(top_frame, text="PDF読み込み", command=self.start_load_pdf, bootstyle="primary")
        self.load_btn.pack(fill=X, pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(top_frame, variable=self.progress_var, maximum=100, bootstyle="primary")
        self.progress_bar.pack(fill=X, pady=5)
        self.status_label = ttk.Label(top_frame, text="待機中", bootstyle="secondary")
        self.status_label.pack(anchor=W)
        
        search_frame = ttk.Frame(self.left_pane, padding=10)
        search_frame.pack(fill=X)
        
        ttk.Label(search_frame, text="検索キーワード:").pack(anchor=W)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(fill=X, pady=5)
        self.search_entry.bind('<Return>', self.perform_search)
        self.search_entry.config(state=DISABLED)
        
        self.search_btn = ttk.Button(search_frame, text="検索", command=self.perform_search, bootstyle="info-outline")
        self.search_btn.pack(fill=X)
        self.search_btn.config(state=DISABLED)
        
        result_frame = ttk.Frame(self.left_pane, padding=10)
        result_frame.pack(fill=BOTH, expand=True)
        
        columns = ('page', 'context', 'index')
        self.tree = ttk.Treeview(result_frame, columns=columns, show='headings', bootstyle="primary")
        self.tree.heading('page', text='ページ', anchor=W)
        self.tree.heading('context', text='文脈', anchor=W)
        self.tree.heading('index', text='IDX', anchor=W) # Hidden column
        
        self.tree.column('page', width=60, stretch=False)
        self.tree.column('context', stretch=True)
        self.tree.column('index', width=0, stretch=False) # Hidden
        
        scrollbar = ttk.Scrollbar(result_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.tree.bind('<Double-1>', self.on_item_double_click)

        # --- Right Pane Contents (Preview) ---
        preview_header = ttk.Frame(self.right_pane)
        preview_header.pack(fill=X, pady=(0, 10))
        
        self.preview_title = ttk.Label(preview_header, text="プレビュー", font=("Helvetica", 12, "bold"))
        self.preview_title.pack(side=LEFT)
        
        close_btn = ttk.Button(preview_header, text="✕", command=self.hide_preview, bootstyle="danger-outline", width=3)
        close_btn.pack(side=RIGHT)
        
        open_ext_btn = ttk.Button(preview_header, text="PDFを開く", command=self.open_current_page_external, bootstyle="secondary-outline")
        open_ext_btn.pack(side=RIGHT, padx=5)

        self.preview_canvas = tk.Canvas(self.right_pane, bg='gray')
        self.preview_canvas.pack(fill=BOTH, expand=True)
        
        h_scroll = ttk.Scrollbar(self.right_pane, orient=HORIZONTAL, command=self.preview_canvas.xview)
        v_scroll = ttk.Scrollbar(self.right_pane, orient=VERTICAL, command=self.preview_canvas.yview)
        self.preview_canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        h_scroll.pack(side=BOTTOM, fill=X)
        v_scroll.pack(side=RIGHT, fill=Y)
        
        self.preview_image_id = None



    def toggle_topmost(self):
        self.root.wm_attributes("-topmost", self.always_on_top_var.get())

    def start_load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return
        
        logging.info(f"Loading PDF: {file_path}")
        self.current_pdf_path = file_path
        self.pdf_data = [] 
        self.hide_preview() 
        
        self.tree.delete(*self.tree.get_children())
        self.search_entry.config(state=DISABLED)
        self.search_btn.config(state=DISABLED)
        self.load_btn.config(state=DISABLED)
        self.progress_var.set(0)
        self.progress_bar.configure(bootstyle="primary") # Reset style to loading (blue)
        filename = os.path.basename(file_path)
        self.status_label.config(text=f"読み込み中: {filename}...")
        
        # Start Thread
        thread = threading.Thread(target=self._load_pdf_thread, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _extract_clean_text(self, page):
        """
        Extract text from page, filtering out ruby (small text).
        Strategy: Identify dominant font size (body text) and ignore text significantly smaller.
        """
        blocks = page.get_text("dict")["blocks"]
        font_sizes = []
        
        # 1. Collect font sizes
        for block in blocks:
            if block["type"] == 0: # text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        # Round to ignoring minor rendering differences
                        font_sizes.append(round(span["size"], 1))
                        
        if not font_sizes:
            return ""
            
        # 2. Find Mode (most frequent) size
        # Most frequent size is likely the body text
        mode_size = Counter(font_sizes).most_common(1)[0][0]
        
        # 3. Filter and Reconstruct
        # Ruby is usually significantly smaller (e.g. 50%). 
        # We set threshold at 85% of body size to be safe (excluding footnotes too).
        threshold = mode_size * 0.85
        
        text_parts = []
        for block in blocks:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["size"] >= threshold:
                            text_parts.append(span["text"])
                    text_parts.append("\n") # Preserve line breaks for structure, though we remove them later
                    
        return "".join(text_parts)

    def _load_pdf_thread(self, file_path):
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            extracted_data = []
            
            for i, page in enumerate(doc):
                text = self._extract_clean_text(page)
                
                norm_text = unicodedata.normalize('NFKC', text)
                search_text = norm_text.replace('\n', '')
                
                extracted_data.append({
                    'page': i + 1,
                    'text': search_text,
                    'orig_text': text
                })
                
                if i % 10 == 0 or i == total_pages - 1:
                    progress = ((i + 1) / total_pages) * 100
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))
            
            self.pdf_data = extracted_data
            self.root.after(0, self._load_complete)
            logging.info(f"Load complete. Pages: {len(self.pdf_data)}")
            
        except Exception as e:
            logging.error(f"Load failed: {e}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("エラー", f"読み込み失敗:\n{e}"))
            self.root.after(0, self._load_reset)

    def _load_complete(self):
        filename = os.path.basename(self.current_pdf_path) if self.current_pdf_path else ""
        self.progress_bar.configure(bootstyle="success") # Change to green on complete
        self.status_label.config(text=f"✔ 読み込み完了: {filename} ({len(self.pdf_data)} ページ)")
        self.load_btn.config(state=NORMAL)
        self.search_entry.config(state=NORMAL)
        self.search_btn.config(state=NORMAL)
        self.search_entry.focus_set()

    def _load_reset(self):
        self.load_btn.config(state=NORMAL)
        self.status_label.config(text="待機中")

    def perform_search(self, event=None):
        raw_query = self.search_entry.get().strip()
        if not raw_query:
            return
        
        logging.info(f"Searching for: {raw_query}")
        query = unicodedata.normalize('NFKC', raw_query).lower()
        
        self.tree.delete(*self.tree.get_children())
        results = []
        
        for item in self.pdf_data:
            page_text_lower = item['text'].lower()
            
            if query in page_text_lower:
                # Find ALL occurrences in the page
                start_search_idx = 0
                hit_counter = 0
                while True:
                    idx = page_text_lower.find(query, start_search_idx)
                    if idx == -1:
                        break
                    
                    start_idx = max(0, idx - 20)
                    end_idx = min(len(item['text']), idx + 20 + len(query))
                    
                    context_str = item['text'][start_idx:end_idx]
                    
                    context = ("..." if start_idx > 0 else "") + \
                              context_str + \
                              ("..." if end_idx < len(item['text']) else "")
                    
                    results.append((item['page'], context, hit_counter))
                    
                    # Move past this match
                    start_search_idx = idx + len(query)
                    hit_counter += 1

        logging.info(f"Found {len(results)} hits")
        for p, ctx, h_idx in results:
            self.tree.insert('', END, values=(f"P.{p}", ctx, h_idx))
            
        filename = os.path.basename(self.current_pdf_path) if self.current_pdf_path else ""
        self.status_label.config(text=f"検索結果: {len(results)} 件 (ファイル: {filename})")

    def on_item_double_click(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        vals = item['values']
        logging.info(f"Double click on: {vals}")
        
        try:
            page_str = str(vals[0])
            page_num = int(page_str.replace("P.", ""))
            
            # Get current search query for highlighting/cropping
            raw_query = self.search_entry.get().strip()
            search_text = unicodedata.normalize('NFKC', raw_query).lower() if raw_query else None
            
            # Get hit index from hidden column (index 2)
            try:
                hit_index = int(vals[2])
            except:
                hit_index = 0
            
            self.show_preview(page_num, search_text, hit_index)
        except Exception as e:
            logging.error(f"Double click error: {e}")

    def _get_smart_crop_rect(self, page, search_text):
        """
        Manually find the bounding box of the search text by reconstructing
        the 'cleaned' text (ruby filtered) and mapping it back to span bboxes.
        """
        if not search_text: return None

        if not search_text: return None


        # 1. Get Blocks & Filter Threshold
        try:
            dict_data = page.get_text("dict")
            blocks = dict_data.get("blocks", [])
        except:
            return None

        font_sizes = []
        for block in blocks:
            if block["type"] == 0: 
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_sizes.append(round(span["size"], 1))
        
        if not font_sizes: return None
        try:
            mode_size = Counter(font_sizes).most_common(1)[0][0]
        except:
            return None
            
        threshold = mode_size * 0.85
        
        # 2. Build Segments (Text + BBox)
        # mimics _extract_clean_text but keeps bboxes
        segments = []
        full_text = ""
        
        # We need to construct text EXACTLY as perform_search sees it (stripped newlines)
        # But _extract_clean_text adds \n. perform_search removes them.
        # So we just concatenate spans directly and ignore line breaks for the mapping.
        
        for block in blocks:
            if block["type"] == 0:
                for line in block["lines"]:
                    for span in line["spans"]:
                        if span["size"] >= threshold:
                            # Normalize segment to match search query format (NFKC + Lower)
                            # Note: This assumes 1-to-1 length mapping mostly. 
                            # If not, the highlight might be slightly off, but good enough for crop.
                            norm_span_text = unicodedata.normalize('NFKC', span["text"]).lower()
                            segments.append({
                                'text': norm_span_text,
                                'bbox': fitz.Rect(span['bbox']),
                                'start': len(full_text)
                            })
                            full_text += norm_span_text
        
        # 3. Find Query and Collect Rects for EACH recurrence
        all_hit_rects = []
        start_search_idx = 0
        
        while True:
            idx = full_text.find(search_text, start_search_idx)
            if idx == -1:
                break
                
            # 4. Calculate Union Rect for THIS hit
            end_idx = idx + len(search_text)
            union_rect = None
            
            for seg in segments:
                seg_start = seg['start']
                seg_end = seg_start + len(seg['text'])
                
                # Check overlap
                if max(seg_start, idx) < min(seg_end, end_idx):
                    if union_rect is None:
                        # CRITICAL: Create a COPY of the rect, do not use reference!
                        union_rect = fitz.Rect(seg['bbox'])
                    else:
                        union_rect.include_rect(seg['bbox'])
            
            if union_rect:
                all_hit_rects.append(union_rect)
                
            start_search_idx = idx + len(search_text)
                    
        return all_hit_rects

    def _detect_orientation(self, page, target_rect):
        """
        Robustly detect text orientation using line context.
        """
        w = target_rect.width
        h = target_rect.height
        if w == 0: return True 
        ratio = h / w
        
        if ratio > 1.2: return True 
        if ratio < 0.8: return False
        
        try:
            center = fitz.Point(target_rect.x0 + w/2, target_rect.y0 + h/2)
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block["type"] == 0:
                    block_rect = fitz.Rect(block["bbox"])
                    if block_rect.contains(center) or block_rect.intersects(target_rect):
                        # Strong Signal: Block Aspect Ratio
                        # Vertical text blocks are usually tall/thin columns
                        if block_rect.height > block_rect.width * 1.2:
                            return True
                        if block_rect.width > block_rect.height * 1.2:
                            return False
                            
                        # If block is ambiguous, check lines
                        for line in block["lines"]:
                            l_rect = fitz.Rect(line["bbox"])
                            if l_rect.contains(center) or l_rect.intersects(target_rect):
                                return l_rect.height > l_rect.width
        except:
            pass
        
        # 3. Fallback
        # If still ambiguous (square-ish), default based on page dimensions?
        # Vertical pages often use vertical text? No, not reliable.
        # But 'poison' (square) failing suggests we are too strict.
        return ratio > 0.9 # Bias slightly towards vertical for squares in this context? 
                           # actually unsafe. Stick to ratio > 1.0 but rely on block check.
        return ratio > 1.0

    def show_preview(self, page_num, search_text=None, hit_index=0):
        if not self.current_pdf_path:
            return

        self.current_preview_page = page_num
        self.preview_title.config(text=f"P.{page_num} プレビュー")
        
        # Add right pane to panedwindow if not currently added
        if str(self.right_pane) not in self.paned_window.panes():
            self.paned_window.add(self.right_pane, weight=1)
            
            # Dynamic Expansion: Widen window to fit preview side-by-side
            # Only expand if currently narrow (approx 500px)
            current_w = self.root.winfo_width()
            current_h = self.root.winfo_height()
            if current_w < 800:
                new_w = current_w * 2
                self.root.geometry(f"{new_w}x{current_h}")
                # Force updates to ensure geometry is applied before setting sash
                self.root.update_idletasks()
                # Restore left pane width to ~500 (half of new width, or original width)
                # Setting sash position 0 to 500
                try:
                    self.paned_window.sashpos(0, 500)
                except:
                    pass

        try:
            # On-Demand Rendering
            doc = fitz.open(self.current_pdf_path)
            # PyMuPDF is 0-indexed
            page = doc.load_page(page_num - 1)
            
            # Default to full page
            clip_rect = page.rect
            zoom_matrix = fitz.Matrix(0.4, 0.4) # Low res for full page
            
            # Smart Crop Logic
            if search_text:
                # Use robust reconstruction to ensure index alignment with search results
                # (page.search_for is faster but searches raw text, which might mismatch filtered results)
                hit_rects = self._get_smart_crop_rect(page, search_text)
                
                target_rect = None
                
                if hit_rects:
                    if len(hit_rects) > hit_index:
                        target_rect = hit_rects[hit_index]
                    else:
                        target_rect = hit_rects[0] # Fallback
                        
                    # Highlight the selected target
                    page.add_highlight_annot(target_rect)
                
                if target_rect:
                    # Auto-Detect Orientation
                    is_vertical = self._detect_orientation(page, target_rect)
                    
                    logging.info(f"Hit rect: {target_rect} (idx={hit_index}), Vertical: {is_vertical} (Highlight Added)")

                    if is_vertical:
                        # Vertical Text Strategy (Tategaki)
                        # Full Height, padded Width
                        padding_x = 150 
                        
                        x0 = max(0, target_rect.x0 - padding_x)
                        y0 = 0 
                        x1 = min(page.rect.width, target_rect.x1 + padding_x)
                        y1 = page.rect.height 
                        
                        clip_rect = fitz.Rect(x0, y0, x1, y1)
                        
                    else:
                        # Horizontal Text Strategy (Yokogaki)
                        # Full Width, padded Height
                        padding_y = 100 
                        
                        x0 = 0 
                        y0 = max(0, target_rect.y0 - padding_y)
                        x1 = page.rect.width 
                        y1 = min(page.rect.height, target_rect.y1 + padding_y)
                        
                        clip_rect = fitz.Rect(x0, y0, x1, y1)

                    zoom_matrix = fitz.Matrix(2.0, 2.0) 
                    logging.info(f"Smart crop applied: {clip_rect} (Vertical={is_vertical})")
                else:
                    logging.info(f"Search text '{search_text}' not found via method")
                    # Fallback to full page if not found
                    zoom_matrix = fitz.Matrix(0.4, 0.4)
                    clip_rect = page.rect

            pix = page.get_pixmap(matrix=zoom_matrix, clip=clip_rect)
            
            # Convert to PIL Image
            img_data = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to ImageTk
            self.current_preview_image = ImageTk.PhotoImage(img_data)
            
            # Update Canvas
            self.preview_canvas.delete("all")
            # Anchor NW (Top Left)
            self.preview_image_id = self.preview_canvas.create_image(0, 0, image=self.current_preview_image, anchor=NW)
            
            self.preview_canvas.config(scrollregion=self.preview_canvas.bbox(ALL))
            
            doc.close()
            
        except Exception as e:
            logging.error(f"Preview error: {e}")
            messagebox.showerror("エラー", f"プレビュー生成に失敗しました: {e}")
            self.hide_preview()

    def hide_preview(self):
        # Check explicit visibility before forgetting to decide on resizing
        is_visible = str(self.right_pane) in self.paned_window.panes()
        
        try:
            self.paned_window.forget(self.right_pane)
        except:
            pass # Ignore if already forgotten
            
        self.current_preview_image = None # Release memory
        self.preview_canvas.delete("all")
        
        if is_visible:
            # Dynamic Shrink: Restore narrow width (Basic Size)
            current_h = self.root.winfo_height()
            # Enforce 500 width, keep current height
            self.root.geometry(f"500x{current_h}")

    def open_current_page_external(self):
        if not self.current_pdf_path: return
        
        # Just open the file (OS default)
        try:
            os.startfile(self.current_pdf_path)
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルを開けませんでした: {e}")

if __name__ == "__main__":
    # Initialize with a default theme, though apply_theme_mode will override it shortly
    # We use 'litera' or 'flatly' as a safe default base
    root = ttk.Window(title="PDFwiki v1.1.0", themename="flatly")
    app = PDFWikiApp(root)
    root.mainloop()
