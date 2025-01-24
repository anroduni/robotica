import cv2
import numpy as np
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, colorchooser
import threading
import serial

# Configura el puerto serial para Arduino
arduino = serial.Serial('COM4', 9600)

root = tk.Tk()
root.title("Control de Brazo Robótico")
root.geometry("1000x900")
root.configure(bg="#641e16")

button_color = "#922b21"
button_hover = "#c0392b"
label_color = "#fdedec"
botonverde = "#27ae60"
button_font = ("Arial", 12, 'bold')
label_font = ("Arial", 14, 'bold')

# Variables globales
cap = None
camera_thread = None
stop_camera = threading.Event()

# Estado global para joints y posiciones
current_joint = tk.StringVar(value="Joint 1")  # Joint seleccionado
degree_value = tk.IntVar(value=10)  # Grados a mover
current_position = []  # Lista temporal de movimientos a guardar
saved_positions = {}  # Diccionario de posiciones guardadas
position_for_color = tk.StringVar(value="")  # Posición a ejecutar al detectar color
selected_color = [125, 50, 75, 165, 255, 255]  # Rango HSV para detección de color

# Funciones de control del brazo robótico
def enviar_comando(comando):
    try:
        arduino.write(comando.encode())
        print(f"Comando enviado: {comando}")
    except Exception as e:
        print(f"Error al enviar comando: {e}")


  
def mover_joint(sentido):
    joint = current_joint.get()
    grados = degree_value.get()  
    if grados <= 0 or grados > 180:
        messagebox.showerror("Error", "Los grados deben estar entre 1 y 180.")
        return

    # Enviar comando al robot
    comando = f"{joint}-{sentido}-{grados}"
    enviar_comando(comando)

    # Registrar movimiento en los temporales
    current_position.append((joint, sentido, grados))
    print(f"Movimiento registrado: Joint={joint}, Sentido={sentido}, Grados={grados}")

def imprimir_temporales():
    if not current_position:
        print("No hay movimientos temporales registrados.")
    else:
        print("Movimientos temporales registrados:")
        for idx, (joint, sentido, grados) in enumerate(current_position):
            print(f"{idx + 1}: Joint={joint}, Sentido={sentido}, Grados={grados}")

def guardar_posicion():
    if not current_position:
        messagebox.showinfo("Información", "No hay movimientos para guardar.")
        return

    nombre = simpledialog.askstring("Guardar Posición", "Nombre de la posición:")
    if nombre:
        saved_positions[nombre] = list(current_position)  # Guardar la lista completa de movimientos
        posiciones_menu["values"] = list(saved_positions.keys())
        color_menu["values"] = list(saved_positions.keys())
        current_position.clear()  # Limpiar la lista temporal
        print(f"Posición guardada como '{nombre}':")
        for joint, sentido, grados in saved_positions[nombre]:
            print(f"Joint={joint}, Sentido={sentido}, Grados={grados}")

def ejecutar_posicion():
    seleccion = posiciones_menu.get()
    if not seleccion or seleccion not in saved_positions:
        messagebox.showerror("Error", "Por favor selecciona una posición válida para ejecutar.")
        return

    movimientos = saved_positions[seleccion]
    print(f"Ejecutando posición '{seleccion}' con los siguientes movimientos:")
    for joint, sentido, grados in movimientos:
        comando = f"{joint}-{sentido}-{grados}"
        enviar_comando(comando)
        print(f"Joint={joint}, Sentido={sentido}, Grados={grados}")

def limpiar_movimientos_temporales():
    current_position.clear()
    print("Movimientos temporales borrados.")

def borrar_posicion_guardada():
    seleccion = posiciones_menu.get()
    if not seleccion or seleccion not in saved_positions:
        messagebox.showerror("Error", "Por favor selecciona una posición válida para borrar.")
        return

    del saved_positions[seleccion]
    posiciones_menu["values"] = list(saved_positions.keys())
    color_menu["values"] = list(saved_positions.keys())
    posiciones_menu.set("")  # Deseleccionar
    position_for_color.set("")  # Limpiar el select de color
    print(f"Posición borrada: {seleccion}")

    seleccion = posiciones_menu.get()
    if not seleccion or seleccion not in saved_positions:
        messagebox.showerror("Error", "Por favor selecciona una posición válida para borrar.")
        return

    del saved_positions[seleccion]
    posiciones_menu["values"] = list(saved_positions.keys())
    color_menu["values"] = list(saved_positions.keys())
    posiciones_menu.set("")  # Deseleccionar
    print(f"Posición borrada: {seleccion}")

# Configuración del color para detección
def ajustar_color():
    global selected_color
    color = colorchooser.askcolor(title="Selecciona un color de detección")
    if color[0]:
        r, g, b = map(int, color[0])
        hsv = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0][0]
        hue_range = 10
        selected_color = [max(0, hsv[0] - hue_range), 50, 50, min(180, hsv[0] + hue_range), 255, 255]
        print(f"Color seleccionado en HSV: {selected_color}")

# Detección automática de color
def ejecutar_por_color():
    seleccion = position_for_color.get()
    if not seleccion or seleccion not in saved_positions:
        messagebox.showerror("Error", "Por favor selecciona una posición válida para ejecutar al detectar color.")
        apagar_camara()
        return

    print(f"Ejecutando posición '{seleccion}' al detectar color seleccionado:")
    for joint, sentido, grados in saved_positions[seleccion]:
        comando = f"{joint}-{sentido}-{grados}"
        enviar_comando(comando)
        print(f"Joint={joint}, Sentido={sentido}, Grados={grados}")

def mostrar_camara():
    global cap
    stop_camera.clear()
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(0)

    while cap.isOpened() and not stop_camera.is_set():
        ret, frame = cap.read()
        if not ret:
            print("Error al acceder a la cámara.")
            break

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Rango dinámico para el color seleccionado
        lower_color = np.array(selected_color[:3])
        upper_color = np.array(selected_color[3:])

        mask = cv2.inRange(hsv, lower_color, upper_color)
        mask = cv2.medianBlur(mask, 7)  # Mejorar la detección con un filtro mediano

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detected = False
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 1500:  # Ajuste del área para evitar detecciones falsas
                detected = True
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame, "Color Detectado", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                ejecutar_por_color()
                break

        cv2.imshow("Cámara - Detección de Color", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if cap is not None and cap.isOpened():
        cap.release()
        print("Cámara liberada en mostrar_camara.")
    cv2.destroyAllWindows()

def iniciar_camara():
    global camera_thread
    if camera_thread is None or not camera_thread.is_alive():
        camera_thread = threading.Thread(target=mostrar_camara, daemon=True)
        camera_thread.start()

def apagar_camara():
    global camera_thread
    stop_camera.set()
    if camera_thread is not None and camera_thread.is_alive():
        camera_thread.join()
        print("Hilo de la cámara terminado.")

def cerrar_app():
    respuesta = messagebox.askyesno("Cerrar", "¿Estás seguro de que deseas cerrar la aplicación?")
    if respuesta:
        apagar_camara()
        root.quit()

def hover_effect(button, color_on_hover, color_on_leave):
    button.bind("<Enter>", lambda e: button.config(bg=color_on_hover))
    button.bind("<Leave>", lambda e: button.config(bg=color_on_leave))

def crear_interfaz():
    # Selección de Joint
    joint_frame = tk.Frame(root, bg="#641e16")
    joint_frame.pack(pady=10)
    tk.Label(joint_frame, text="Seleccionar Joint:", bg="#641e16", fg=label_color, font=label_font).grid(row=0, column=0, padx=10, pady=5)
    joints_menu = ttk.Combobox(joint_frame, textvariable=current_joint, values=[f"Joint {i}" for i in range(1, 7)], state="readonly")
    joints_menu.grid(row=0, column=1, padx=10, pady=5)

    # Control de grados
    degrees_frame = tk.Frame(root, bg="#641e16")
    degrees_frame.pack(pady=10)
    tk.Label(degrees_frame, text="Grados a mover:", bg="#641e16", fg=label_color, font=label_font).grid(row=0, column=0, padx=10, pady=5)
    tk.Entry(degrees_frame, textvariable=degree_value, font=button_font).grid(row=0, column=1, padx=10, pady=5)

    # Botones de movimiento
    movement_frame = tk.Frame(root, bg="#641e16")
    movement_frame.pack(pady=20)
    positive_button = tk.Button(movement_frame, text="Positivo",  activebackground="#f1948a", bg=button_color, fg="white", font=button_font, width=10, height=2, command=lambda: mover_joint("+"))
    positive_button.grid(row=0, column=0, padx=10, pady=10)
    hover_effect(positive_button, button_hover, button_color)

    negative_button = tk.Button(movement_frame, text="Negativo",  activebackground="#f1948a", bg=button_color, fg="white", font=button_font, width=10, height=2, command=lambda: mover_joint("-"))
    negative_button.grid(row=0, column=1, padx=10, pady=10)
    hover_effect(negative_button, button_hover, button_color)

    # Guardar y seleccionar posiciones
    position_frame = tk.Frame(root, bg="#641e16")
    position_frame.pack(pady=20)

    imprimir_button = tk.Button(position_frame, text="Imprimir Temporales", bg=button_color,  activebackground="#f1948a", fg="white", font=button_font, width=20, height=2, command=imprimir_temporales)
    imprimir_button.grid(row=0, column=0, padx=10, pady=10, )
    hover_effect(imprimir_button, button_hover, button_color)

    limpiar_button = tk.Button(position_frame, text="Limpiar Movimientos", activebackground="#ffd05f", bg="orange", fg="white", font=button_font, width=20, height=2, command=limpiar_movimientos_temporales)
    limpiar_button.grid(row=0, column=1, padx=10, pady=10)
    hover_effect(limpiar_button, "#ffd05f", "orange")

    guardar_button = tk.Button(position_frame, text="Guardar Posición", bg=button_color,  activebackground="#f1948a", fg="white", font=button_font, width=15, height=2, command=guardar_posicion)
    guardar_button.grid(row=0, column=2, padx=10, pady=10)
    hover_effect(guardar_button, button_hover, button_color)

    ejecutar_button = tk.Button(position_frame, text="Ejecutar Posición", bg="green", activebackground="#57dd90", fg="white", font=button_font, width=15, height=2, command=ejecutar_posicion)
    ejecutar_button.grid(row=1, column=0, padx=10, pady=30)
    hover_effect(ejecutar_button, botonverde, "green")

    global posiciones_menu
    posiciones_menu = ttk.Combobox(position_frame, state="readonly", width=20)
    posiciones_menu.grid(row=1, column=1, padx=10, pady=30)

    borrar_button = tk.Button(position_frame, text="Borrar Posición", activebackground="#fd7676", bg="red", fg="white", font=button_font, width=15, height=2, command=borrar_posicion_guardada)
    borrar_button.grid(row=1, column=2, padx=10, pady=30)
    hover_effect(borrar_button, "#fd7676", "red")

    

    # Configuración de detección de color
    color_frame = tk.Frame(root, bg="#641e16")
    color_frame.pack(pady=20)
    tk.Label(color_frame, text="Ejecutar por detección de color:", bg="#641e16", fg=label_color, font=label_font).grid(row=0, column=0, padx=10, pady=5)

    global color_menu
    color_menu = ttk.Combobox(color_frame, textvariable=position_for_color, state="readonly", width=20)
    color_menu.grid(row=0, column=1, padx=10, pady=5)

    ajustar_color_button = tk.Button(color_frame, text="Ajustar Color", bg=button_color,  activebackground="#f1948a", fg="white", font=button_font, width=15, height=2, command=ajustar_color)
    ajustar_color_button.grid(row=0, column=2, padx=10, pady=10)
    hover_effect(ajustar_color_button, button_hover, button_color)

    # Controles de cámara
    camera_frame = tk.Frame(root, bg="#641e16")
    camera_frame.pack(pady=20)
    ver_camara_button = tk.Button(camera_frame, text="Ver Cámara", bg=button_color,  activebackground="#f1948a", fg="white", font=button_font, width=15, height=2, command=iniciar_camara)
    ver_camara_button.grid(row=0, column=0, padx=10, pady=10)
    hover_effect(ver_camara_button, button_hover, button_color)

    apagar_camara_button = tk.Button(camera_frame, text="Apagar Cámara",  activebackground="#f1948a", bg=button_color, fg="white", font=button_font, width=15, height=2, command=apagar_camara)
    apagar_camara_button.grid(row=0, column=1, padx=10, pady=10)
    hover_effect(apagar_camara_button, button_hover, button_color)

    # Botón de cierre
    cerrar_button = tk.Button(root, text="Cerrar App",  activebackground="#f1948a", bg=button_color, fg="white", font=button_font, width=15, height=2, command=cerrar_app)
    cerrar_button.pack(side="bottom", pady=30)
    hover_effect(cerrar_button, button_hover, button_color)

crear_interfaz()
root.mainloop()
