import tkinter as tk
import time

def main():
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.geometry("300x100")
    
    # Center splash screen
    splash.update_idletasks()
    width = splash.winfo_width()
    frm_width = splash.winfo_rootx() - splash.winfo_x()
    win_width = width + 2 * frm_width
    height = splash.winfo_height()
    titlebar_height = splash.winfo_rooty() - splash.winfo_y()
    win_height = height + titlebar_height + frm_width
    x = splash.winfo_screenwidth() // 2 - win_width // 2
    y = splash.winfo_screenheight() // 2 - win_height // 2
    splash.geometry(f'{width}x{height}+{x}+{y}')
    
    tk.Label(splash, text="就活サポートアプリ起動中...", font=("Helvetica", 14)).pack(expand=True)
    splash.update()
    
    time.sleep(2) # pretend we are loading
    
    splash.destroy()
    
    # Create the actual app root
    app = tk.Tk()
    app.title("Main App")
    app.geometry("400x300")
    tk.Label(app, text="Main App Interface").pack(expand=True)
    app.mainloop()

if __name__ == "__main__":
    main()
