from tkinter import Tk, Label

root = Tk()
root.title("Test Window")
root.geometry("300x150")

label = Label(root, text="Hello World")
label.pack(pady=50)

root.mainloop()

