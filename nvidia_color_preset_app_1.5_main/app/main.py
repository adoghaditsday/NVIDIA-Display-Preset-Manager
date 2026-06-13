from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

import customtkinter as ctk

try:
    from app.presets import PresetStore, ColorPreset
    from app.color_backend import HybridColorBackend, ColorBackendError
    from app.hotkeys import HotkeyManager, parse_hotkey
    from app.tray import TrayController
    from app.icon_manager import active_icon_ico, active_icon_png, install_custom_icon, clear_custom_icon
except ImportError:
    from presets import PresetStore, ColorPreset
    from color_backend import HybridColorBackend, ColorBackendError
    from hotkeys import HotkeyManager, parse_hotkey
    from tray import TrayController
    from icon_manager import active_icon_ico, active_icon_png, install_custom_icon, clear_custom_icon

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class NvidiaColorPresetApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NVIDIA Color Presets")
        self.geometry("820x680")
        self.minsize(780, 620)

        self.store = PresetStore()
        self.presets = self.store.load_all()
        self.settings = self.store.load_settings()
        self.settings.setdefault("custom_icon_enabled", False)
        self.current_name = next(iter(self.presets.keys()))

        try:
            self.backend = HybridColorBackend()
        except ColorBackendError as exc:
            messagebox.showerror("Backend Error", str(exc))
            raise

        self.hotkeys = HotkeyManager(self.apply_preset_by_name_threadsafe)
        self.tray = TrayController(self.show_from_tray, self.exit_app, self.apply_preset_by_name_threadsafe, self.get_tray_icon_path)

        self.apply_window_icon()
        self._build_menu()
        self._build_ui()
        self.refresh_preset_list()
        self.load_preset_into_sliders(self.current_name)
        self.restart_hotkeys()
        self.tray.start(self.presets.keys())

        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="New", command=self.new_preset)
        file_menu.add_command(label="Edit", command=self.save_current_to_selected)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.exit_app)
        menu.add_cascade(label="File", menu=file_menu)

        icon_menu = tk.Menu(menu, tearoff=0)
        icon_menu.add_command(label="Change Custom Icon...", command=self.choose_custom_icon)
        icon_menu.add_command(label="Use Default Icon", command=self.use_default_icon)
        menu.add_cascade(label="Icon", menu=icon_menu)
        self.config(menu=menu)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=210)
        self.sidebar.grid(row=0, column=0, sticky="nswe", padx=12, pady=12)
        self.sidebar.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self.sidebar, text="Presets", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=12, pady=(12, 8), sticky="w")
        self.preset_box = ctk.CTkScrollableFrame(self.sidebar, width=180)
        self.preset_box.grid(row=2, column=0, sticky="nswe", padx=12, pady=8)

        ctk.CTkButton(self.sidebar, text="Apply Selected", command=self.apply_selected).grid(row=3, column=0, padx=12, pady=(8, 4), sticky="ew")
        ctk.CTkButton(self.sidebar, text="New", command=self.new_preset).grid(row=4, column=0, padx=12, pady=4, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Save/Edit", command=self.save_current_to_selected).grid(row=5, column=0, padx=12, pady=4, sticky="ew")
        ctk.CTkButton(self.sidebar, text="Delete", fg_color="#713232", hover_color="#8b3c3c", command=self.delete_selected).grid(row=6, column=0, padx=12, pady=(4, 12), sticky="ew")

        self.main = ctk.CTkTabview(self)
        self.main.grid(row=0, column=1, sticky="nswe", padx=(0, 12), pady=12)
        self.tab_controls = self.main.add("Controls")
        self.tab_preferences = self.main.add("Preferences")

        self.name_var = tk.StringVar(value="")
        ctk.CTkLabel(self.tab_controls, textvariable=self.name_var, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", padx=20, pady=(20, 5))

        self.brightness = tk.IntVar(value=50)
        self.contrast = tk.IntVar(value=50)
        self.gamma = tk.DoubleVar(value=1.0)
        self.digital_vibrance = tk.IntVar(value=50)
        self.red_channel = tk.IntVar(value=100)
        self.green_channel = tk.IntVar(value=100)
        self.blue_channel = tk.IntVar(value=100)

        self._slider(self.tab_controls, "Brightness", self.brightness, 0, 100, 1)
        self._slider(self.tab_controls, "Contrast", self.contrast, 0, 100, 1)
        self._slider(self.tab_controls, "Gamma", self.gamma, 0.5, 2.5, 0.01)
        self._slider(self.tab_controls, "Digital Vibrance", self.digital_vibrance, 0, 100, 1)
        ctk.CTkLabel(self.tab_controls, text="RGB Channel Balance (gamma-ramp based)", font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(8, 0))
        self._slider(self.tab_controls, "Red Channel", self.red_channel, 0, 200, 1)
        self._slider(self.tab_controls, "Green Channel", self.green_channel, 0, 200, 1)
        self._slider(self.tab_controls, "Blue Channel", self.blue_channel, 0, 200, 1)

        controls = ctk.CTkFrame(self.tab_controls)
        controls.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(controls, text="Apply Current Sliders", command=self.apply_current_values).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(controls, text="Save as New Preset", command=self.new_preset).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(controls, text="Save Over Selected", command=self.save_current_to_selected).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(controls, text="Restore Neutral", command=self.restore_neutral).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(controls, text="Reset RGB", command=self.reset_rgb_balance).pack(side="left", padx=8, pady=10)

        self.status_var = tk.StringVar(value="Ready.")
        ctk.CTkLabel(self.tab_controls, textvariable=self.status_var).pack(anchor="w", padx=20, pady=(8, 0))

        ctk.CTkLabel(self.tab_preferences, text="Appearance", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(22, 8))
        self.icon_status_var = tk.StringVar(value=self._icon_status_text())
        ctk.CTkLabel(self.tab_preferences, textvariable=self.icon_status_var).pack(anchor="w", padx=20, pady=(0, 8))
        icon_controls = ctk.CTkFrame(self.tab_preferences)
        icon_controls.pack(fill="x", padx=20, pady=(0, 14))
        ctk.CTkButton(icon_controls, text="Change Custom Icon...", command=self.choose_custom_icon).pack(side="left", padx=8, pady=10)
        ctk.CTkButton(icon_controls, text="Use Default Icon", command=self.use_default_icon).pack(side="left", padx=8, pady=10)

        ctk.CTkLabel(self.tab_preferences, text="Hotkeys", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(8, 8))
        self.hotkeys_enabled = tk.BooleanVar(value=bool(self.settings.get("hotkeys_enabled", False)))
        ctk.CTkCheckBox(self.tab_preferences, text="Enable preset hotkeys", variable=self.hotkeys_enabled, command=self.save_hotkeys).pack(anchor="w", padx=20, pady=(0, 12))
        ctk.CTkLabel(self.tab_preferences, text="Hotkeys are limited to two commands, such as CTRL+F7 or ALT+G.").pack(anchor="w", padx=20, pady=(0, 8))

        self.hotkey_frame = ctk.CTkScrollableFrame(self.tab_preferences)
        self.hotkey_frame.pack(fill="both", expand=True, padx=20, pady=12)
        self.hotkey_entries: dict[str, ctk.CTkEntry] = {}
        ctk.CTkButton(self.tab_preferences, text="Save Hotkeys", command=self.save_hotkeys).pack(anchor="e", padx=20, pady=(0, 16))

    def _slider(self, parent, label: str, variable, from_: float, to: float, step: float) -> None:
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", padx=20, pady=10)
        value_label = ctk.CTkLabel(frame, text="")
        value_label.pack(side="right", padx=12)
        ctk.CTkLabel(frame, text=label, width=110, anchor="w").pack(side="left", padx=12)
        slider = ctk.CTkSlider(frame, from_=from_, to=to, variable=variable)
        slider.pack(side="left", fill="x", expand=True, padx=10, pady=16)

        def update(*_):
            val = variable.get()
            if isinstance(val, float):
                value_label.configure(text=f"{val:.2f}")
            else:
                value_label.configure(text=str(val))
        variable.trace_add("write", update)
        update()

    def _icon_status_text(self) -> str:
        if self.settings.get("custom_icon_enabled", False):
            return "Current icon: Custom"
        return "Current icon: Default"

    def get_tray_icon_path(self) -> str:
        return str(active_icon_png(self.settings))

    def apply_window_icon(self) -> None:
        try:
            ico_path = active_icon_ico(self.settings)
            if ico_path.exists():
                self.iconbitmap(str(ico_path))
        except Exception:
            # Some Tk builds reject .ico paths while running from source; tray icon can still work.
            pass

    def choose_custom_icon(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Choose Custom Icon",
            filetypes=[
                ("Image/Icon files", "*.ico *.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        try:
            install_custom_icon(file_path)
        except Exception as exc:
            messagebox.showerror("Custom Icon", str(exc))
            return
        self.settings["custom_icon_enabled"] = True
        self.store.save_settings(self.settings)
        self.apply_window_icon()
        self.icon_status_var.set(self._icon_status_text())
        self.tray.start(self.presets.keys())
        self.status_var.set("Custom icon applied. Rebuild the EXE to bake it into the executable file icon.")

    def use_default_icon(self) -> None:
        clear_custom_icon()
        self.settings["custom_icon_enabled"] = False
        self.store.save_settings(self.settings)
        self.apply_window_icon()
        self.icon_status_var.set(self._icon_status_text())
        self.tray.start(self.presets.keys())
        self.status_var.set("Default icon restored.")

    def refresh_preset_list(self) -> None:
        for w in self.preset_box.winfo_children():
            w.destroy()
        for name in self.presets.keys():
            btn = ctk.CTkButton(self.preset_box, text=name, anchor="w", command=lambda n=name: self.select_preset(n))
            btn.pack(fill="x", padx=4, pady=4)
        self.refresh_hotkey_rows()

    def refresh_hotkey_rows(self) -> None:
        for w in self.hotkey_frame.winfo_children():
            w.destroy()
        self.hotkey_entries.clear()
        hotkeys = self.settings.get("hotkeys", {})
        for name in self.presets.keys():
            row = ctk.CTkFrame(self.hotkey_frame)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=name, width=180, anchor="w").pack(side="left", padx=8, pady=8)
            entry = ctk.CTkEntry(row, placeholder_text="CTRL+F7")
            entry.insert(0, hotkeys.get(name, ""))
            entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)
            self.hotkey_entries[name] = entry

    def select_preset(self, name: str) -> None:
        self.current_name = name
        self.load_preset_into_sliders(name)

    def load_preset_into_sliders(self, name: str) -> None:
        preset = self.presets[name]
        self.name_var.set(name)
        self.brightness.set(preset.brightness)
        self.contrast.set(preset.contrast)
        self.gamma.set(preset.gamma)
        self.digital_vibrance.set(getattr(preset, "digital_vibrance", 50))
        self.red_channel.set(getattr(preset, "red_channel", 100))
        self.green_channel.set(getattr(preset, "green_channel", 100))
        self.blue_channel.set(getattr(preset, "blue_channel", 100))

    def _current_preset(self) -> ColorPreset:
        return ColorPreset(
            self.brightness.get(),
            self.contrast.get(),
            self.gamma.get(),
            self.digital_vibrance.get(),
            self.red_channel.get(),
            self.green_channel.get(),
            self.blue_channel.get(),
        )

    def apply_current_values(self) -> None:
        p = self._current_preset().normalized()
        result = self.backend.apply(p.brightness, p.contrast, p.gamma, p.digital_vibrance, p.red_channel, p.green_channel, p.blue_channel)
        self.status_var.set(result.message)

    def apply_selected(self) -> None:
        self.apply_preset_by_name_threadsafe(self.current_name)

    def apply_preset_by_name_threadsafe(self, name: str) -> None:
        def run():
            if name not in self.presets:
                return
            self.current_name = name
            self.load_preset_into_sliders(name)
            self.apply_current_values()
        try:
            self.after(0, run)
        except Exception:
            run()

    def new_preset(self) -> None:
        name = simpledialog.askstring("New Preset", "Preset name:", parent=self)
        if not name:
            return
        name = name.strip()
        if not name:
            return
        self.presets[name] = self._current_preset().normalized()
        self.store.save_all(self.presets)
        self.current_name = name
        self.name_var.set(name)
        self.settings.setdefault("hotkeys", {}).setdefault(name, "")
        self.store.save_settings(self.settings)
        self.refresh_preset_list()
        self.tray.start(self.presets.keys())

    def save_current_to_selected(self) -> None:
        self.presets[self.current_name] = self._current_preset().normalized()
        self.store.save_all(self.presets)
        self.status_var.set(f"Saved preset: {self.current_name}")

    def delete_selected(self) -> None:
        if len(self.presets) <= 1:
            messagebox.showwarning("Delete Preset", "At least one preset must remain.")
            return
        if not messagebox.askyesno("Delete Preset", f"Delete '{self.current_name}'?"):
            return
        self.presets.pop(self.current_name, None)
        self.settings.get("hotkeys", {}).pop(self.current_name, None)
        self.store.save_all(self.presets)
        self.store.save_settings(self.settings)
        self.current_name = next(iter(self.presets.keys()))
        self.refresh_preset_list()
        self.load_preset_into_sliders(self.current_name)
        self.restart_hotkeys()
        self.tray.start(self.presets.keys())

    def restore_neutral(self) -> None:
        self.brightness.set(50)
        self.contrast.set(50)
        self.gamma.set(1.0)
        self.digital_vibrance.set(50)
        self.red_channel.set(100)
        self.green_channel.set(100)
        self.blue_channel.set(100)
        self.apply_current_values()

    def reset_rgb_balance(self) -> None:
        self.red_channel.set(100)
        self.green_channel.set(100)
        self.blue_channel.set(100)
        self.apply_current_values()

    def save_hotkeys(self) -> None:
        hotkeys = {}
        for preset, entry in self.hotkey_entries.items():
            value = entry.get().strip().upper()
            if value:
                try:
                    parse_hotkey(value)
                except ValueError as exc:
                    messagebox.showerror("Invalid Hotkey", f"{preset}: {exc}")
                    return
            hotkeys[preset] = value
        self.settings["hotkeys_enabled"] = bool(self.hotkeys_enabled.get())
        self.settings["hotkeys"] = hotkeys
        self.store.save_settings(self.settings)
        self.restart_hotkeys()
        self.status_var.set("Hotkey preferences saved.")

    def restart_hotkeys(self) -> None:
        self.hotkeys.stop()
        if self.settings.get("hotkeys_enabled"):
            mapping = {k: v for k, v in self.settings.get("hotkeys", {}).items() if k in self.presets and v}
            self.hotkeys.start(mapping)

    def minimize_to_tray(self) -> None:
        self.withdraw()

    def show_from_tray(self) -> None:
        self.after(0, lambda: (self.deiconify(), self.lift(), self.focus_force()))

    def exit_app(self) -> None:
        self.hotkeys.stop()
        self.tray.stop()
        self.destroy()


def main() -> None:
    app = NvidiaColorPresetApp()
    app.mainloop()


if __name__ == "__main__":
    main()
