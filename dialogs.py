import tkinter as tk
from tkinter import ttk


class CountdownDialog(tk.Toplevel):
    """Dialog mit Countdown-Timer für kritische Aktionen"""

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        countdown_seconds: int = 5,
        icon: str = "warning"
    ):
        super().__init__(parent)
        self.parent = parent
        self.countdown_seconds = max(1, int(countdown_seconds))
        self.remaining_seconds = self.countdown_seconds
        self.icon = icon
        self._result = False

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)

        self._build_ui(message)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.update_idletasks()
        self._center_window(parent)

    def _build_ui(self, message: str) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        icon_map = {
            "warning": "⚠️",
            "error": "❌",
            "question": "❓",
        }
        icon_symbol = icon_map.get(self.icon, "⚠️")

        ttk.Label(container, text=icon_symbol, font=("Segoe UI", 20)).pack(pady=(0, 8))
        ttk.Label(container, text=message, justify="left", wraplength=420).pack(anchor="w", pady=(0, 12))

        self.countdown_label = ttk.Label(
            container,
            text=f"Fortfahren möglich in {self.remaining_seconds} Sekunden...",
            foreground="#B71C1C"
        )
        self.countdown_label.pack(anchor="w", pady=(0, 14))

        button_row = ttk.Frame(container)
        button_row.pack(fill="x")

        self.btn_cancel = ttk.Button(button_row, text="Abbrechen", command=self._on_cancel)
        self.btn_cancel.pack(side="right")

        self.btn_continue = ttk.Button(button_row, text="Fortfahren", command=self._on_confirm, state="disabled")
        self.btn_continue.pack(side="right", padx=(0, 8))

    def _center_window(self, parent: tk.Tk) -> None:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        x = parent_x + max(0, (parent_w - width) // 2)
        y = parent_y + max(0, (parent_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _tick(self) -> None:
        if self.remaining_seconds <= 0:
            self.countdown_label.config(text="Sie können jetzt fortfahren.", foreground="#2E7D32")
            self.btn_continue.config(state="normal")
            return

        self.countdown_label.config(
            text=f"Fortfahren möglich in {self.remaining_seconds} Sekunden..."
        )
        self.remaining_seconds -= 1
        self.after(1000, self._tick)

    def _on_confirm(self) -> None:
        self._result = True
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = False
        self.destroy()

    def show(self) -> bool:
        """Zeigt Dialog und wartet auf Benutzer-Entscheidung"""
        self.grab_set()
        self.focus_set()
        self._tick()
        self.wait_window(self)
        return self._result


class ConfirmationDialog(tk.Toplevel):
    """Dialog mit Text-Eingabe zur Bestätigung"""

    def __init__(
        self,
        parent: tk.Tk,
        title: str,
        message: str,
        required_text: str = "LÖSCHEN"
    ):
        super().__init__(parent)
        self.parent = parent
        self.required_text = required_text
        self._result = False

        self.title(title)
        self.resizable(False, False)
        self.transient(parent)

        self._build_ui(message)
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.update_idletasks()
        self._center_window(parent)

    def _build_ui(self, message: str) -> None:
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        ttk.Label(container, text="🔒", font=("Segoe UI", 20)).pack(pady=(0, 8))
        ttk.Label(container, text=message, justify="left", wraplength=420).pack(anchor="w", pady=(0, 10))

        self.var_confirm = tk.StringVar()
        self.entry = ttk.Entry(container, textvariable=self.var_confirm, width=32)
        self.entry.pack(fill="x", pady=(0, 8))
        self.entry.bind("<KeyRelease>", lambda _: self._update_confirm_state())
        self.entry.bind("<Return>", lambda _: self._on_confirm())

        self.hint_label = ttk.Label(
            container,
            text=f"Bitte exakt eingeben: {self.required_text}",
            foreground="#666666"
        )
        self.hint_label.pack(anchor="w", pady=(0, 12))

        button_row = ttk.Frame(container)
        button_row.pack(fill="x")

        self.btn_cancel = ttk.Button(button_row, text="Abbrechen", command=self._on_cancel)
        self.btn_cancel.pack(side="right")

        self.btn_confirm = ttk.Button(button_row, text="Bestätigen", command=self._on_confirm, state="disabled")
        self.btn_confirm.pack(side="right", padx=(0, 8))

    def _center_window(self, parent: tk.Tk) -> None:
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()

        x = parent_x + max(0, (parent_w - width) // 2)
        y = parent_y + max(0, (parent_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _update_confirm_state(self) -> None:
        is_valid = self.var_confirm.get().strip() == self.required_text
        self.btn_confirm.config(state="normal" if is_valid else "disabled")

    def _on_confirm(self) -> None:
        if self.var_confirm.get().strip() != self.required_text:
            return
        self._result = True
        self.destroy()

    def _on_cancel(self) -> None:
        self._result = False
        self.destroy()

    def show(self) -> bool:
        """Zeigt Dialog und wartet auf korrekte Texteingabe"""
        self.grab_set()
        self.entry.focus_set()
        self.wait_window(self)
        return self._result
