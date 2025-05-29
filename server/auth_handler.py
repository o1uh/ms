import hashlib
import secrets

def generate_salt():
    """Генерирует случайную соль."""
    return secrets.token_hex(16) # 32-символьная шестнадцатеричная строка

def hash_password(password, salt):
    """Хэширует пароль с использованием соли (PBKDF2-HMAC-SHA256)."""
    salted_password = salt + password
    # Рекомендуется использовать соль как байты для параметра salt в pbkdf2_hmac
    # и пароль+соль как байты для первого параметра.
    hashed = hashlib.pbkdf2_hmac(
        'sha256',                         # Используемый хэш-алгоритм
        salted_password.encode('utf-8'),  # Пароль + соль, закодированные в байты
        salt.encode('utf-8'),             # Соль также как байты
        100000,                           # Количество итераций (можно увеличить для большей безопасности)
        dklen=128                         # Длина получаемого ключа в байтах (128 байт = 1024 бит)
    )
    return hashed.hex() # Возвращаем хэш в виде шестнадцатеричной строки (256 символов)

def verify_password(stored_password_hash, salt, provided_password):
    """Проверяет предоставленный пароль по сохраненному хэшу и соли."""
    # Хэшируем предоставленный пароль с той же солью и параметрами
    hashed_provided_password = hash_password(provided_password, salt)
    # Сравниваем полученный хэш с сохраненным
    return stored_password_hash == hashed_provided_password
