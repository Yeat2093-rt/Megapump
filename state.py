# Хранилище последнего найденного сигнала
last_signal = None

def set_last_signal(data):
    global last_signal
    last_signal = data

def get_last_signal():
    return last_signal
