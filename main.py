import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import threading
import os
import sys

class PDFWikiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDFwiki")
        self.root.geometry("400x600")
        
        # Data storage
        self.pdf_data = [] # List of dicts: [{'page': 1, 'text': '...'}, ...]
        self.current_pdf_path = None
        
        # GUI Setup
        self.setup_ui()
        
    def setup_ui(self):
        # Top Frame: Controls
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)
        
        # Always on top checkbox
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.top_check = ttk.Checkbutton(
            top_frame, 
            text="常に手前に表示", 
            variable=self.always_on_top_var,
            command=self.toggle_topmost
        )
        self.top_check.pack(anchor=tk.W)
        
        # Load Button
        self.load_btn = ttk.Button(top_frame, text="PDF読み込み", command=self.start_load_pdf)
        self.load_btn.pack(fill=tk.X, pady=5)
        
        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(top_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(top_frame, text="待機中")
        self.status_label.pack(anchor=tk.W)
        
        # Search Frame
        search_frame = ttk.Frame(self.root, padding=10)
        search_frame.pack(fill=tk.X)
        
        ttk.Label(search_frame, text="検索キーワード:").pack(anchor=tk.W)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(fill=tk.X, pady=5)
        self.search_entry.bind('<Return>', self.perform_search)
        self.search_entry.config(state=tk.DISABLED)
        
        self.search_btn = ttk.Button(search_frame, text="検索", command=self.perform_search)
        self.search_btn.pack(fill=tk.X)
        self.search_btn.config(state=tk.DISABLED)
        
        # Results Area
        result_frame = ttk.Frame(self.root, padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for results
        columns = ('page', 'context')
        self.tree = ttk.Treeview(result_frame, columns=columns, show='headings')
        self.tree.heading('page', text='ページ', anchor=tk.W)
        self.tree.heading('context', text='文脈', anchor=tk.W)
        
        self.tree.column('page', width=60, stretch=False)
        self.tree.column('context', stretch=True)
        
        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind('<Double-1>', self.on_item_double_click)

    def toggle_topmost(self):
        self.root.wm_attributes("-topmost", self.always_on_top_var.get())

    def start_load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return
        
        self.current_pdf_path = file_path
        self.pdf_data = [] # Clear previous data
        
        # UI Reset
        self.tree.delete(*self.tree.get_children())
        self.search_entry.config(state=tk.DISABLED)
        self.search_btn.config(state=tk.DISABLED)
        self.load_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_label.config(text="読み込み中...")
        
        # Start Thread
        thread = threading.Thread(target=self._load_pdf_thread, args=(file_path,))
        thread.daemon = True
        thread.start()

    def _load_pdf_thread(self, file_path):
        import unicodedata
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            
            extracted_data = []
            
            for i, page in enumerate(doc):
                text = page.get_text("text")
                # Normalize text (NFKC) to handle half-width/full-width uniformly
                norm_text = unicodedata.normalize('NFKC', text)
                
                # For Japanese search, newlines often break words (e.g., "日\n本\n語").
                # Removing newlines ensures "日本語" is searchable.
                # Side effect: "Word\nWord" becomes "WordWord". Acceptable for this use case.
                search_text = norm_text.replace('\n', '')
                
                extracted_data.append({
                    'page': i + 1,
                    'text': search_text,
                    'orig_text': text # Keep original for potential debug or fallback
                })
                
                # Update progress sparingly
                if i % 10 == 0 or i == total_pages - 1:
                    progress = ((i + 1) / total_pages) * 100
                    self.root.after(0, lambda p=progress: self.progress_var.set(p))
            
            self.pdf_data = extracted_data
            self.root.after(0, self._load_complete)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("エラー", f"PDFの読み込みに失敗しました:\n{e}"))
            self.root.after(0, self._load_reset)

    def _load_complete(self):
        self.status_label.config(text=f"読み込み完了 ({len(self.pdf_data)} ページ)")
        self.load_btn.config(state=tk.NORMAL)
        self.search_entry.config(state=tk.NORMAL)
        self.search_btn.config(state=tk.NORMAL)
        self.search_entry.focus_set()

    def _load_reset(self):
        self.load_btn.config(state=tk.NORMAL)
        self.status_label.config(text="待機中")

    def perform_search(self, event=None):
        import unicodedata
        raw_query = self.search_entry.get().strip()
        if not raw_query:
            return
        
        # Normalize and lower case for search
        query = unicodedata.normalize('NFKC', raw_query).lower()
        
        self.tree.delete(*self.tree.get_children())
        results = []
        
        for item in self.pdf_data:
            # Case insensitive search
            page_text_lower = item['text'].lower()
            
            if query in page_text_lower:
                idx = page_text_lower.find(query)
                start_idx = max(0, idx - 20)
                end_idx = min(len(item['text']), idx + 20 + len(query))
                
                # Use the non-lowercased 'text' for display to preserve casing
                context_str = item['text'][start_idx:end_idx]
                
                context = ("..." if start_idx > 0 else "") + \
                          context_str + \
                          ("..." if end_idx < len(item['text']) else "")
                
                results.append((item['page'], context))
        
        # Update UI
        for p, ctx in results:
            self.tree.insert('', tk.END, values=(f"P.{p}", ctx))
            
        self.status_label.config(text=f"検索結果: {len(results)} 件")

    def on_item_double_click(self, event):
        if not self.current_pdf_path:
            return
            
        try:
            # Open file
            os.startfile(self.current_pdf_path)
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルを開けませんでした:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = PDFWikiApp(root)
    root.mainloop()
