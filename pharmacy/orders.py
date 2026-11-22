"""Заказы из чата. Запуск на Mac: python3 orders.py"""
import argparse
import hashlib
import json
import re
from decimal import Decimal
from getpass import getpass
from pathlib import Path


HEADER = re.compile(
    r"(\d+)\.\s*Индивидуальный\s+заказ\s+(.+?)(?:\s*[-–—]\s*|\s+)(\d+)\s+"
    r"(?:день|дня|дней)\s+Кол-?во\s*:\s*(\d+)", re.IGNORECASE
)
COMPONENT = re.compile(
    r"[•*\-]\s*(.+?)\s+(?:[-–—]\s+)?(\d{1,9}(?:[.,]\d{1,3})?)\s*мг", re.IGNORECASE
)


def parse_orders(text):
    orders = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        header = HEADER.fullmatch(line)
        if header:
            number, form, days, quantity = header.groups()
            if min(int(number), int(days), int(quantity)) < 1:
                raise ValueError(f"Строка {line_no}: номер, срок и количество должны быть больше нуля")
            orders.append({"number": int(number), "form": form.strip(), "duration_days": int(days),
                           "quantity": int(quantity), "components": []})
            continue

        component = COMPONENT.fullmatch(line)
        if not component or not orders:
            raise ValueError(f"Строка {line_no}: не удалось разобрать «{line}»")
        name, dose = component.groups()
        name = ' '.join(name.split())
        if name.endswith(('-', '–', '—')):
            raise ValueError(f"Строка {line_no}: проверь разделитель и дозировку")
        if name.lower() in ('nацетилцистеин', 'n-ацетилцистеин'):
            name = 'N-Ацетилцистеин'
        dose = Decimal(dose.replace(',', '.'))
        if dose <= 0:
            raise ValueError(f"Строка {line_no}: дозировка должна быть больше нуля")
        orders[-1]['components'].append({'name': name, 'dosage_mg': dose})

    if not orders:
        raise ValueError('Файл не содержит заказов')
    for order in orders:
        if not order['components']:
            raise ValueError(f"У заказа {order['number']} нет компонентов")
    return orders


def calculate_totals(orders):
    totals = {}
    for order in orders:
        for component in order['components']:
            name = component['name']
            used = component['dosage_mg'] * order['quantity']
            totals[name] = totals.get(name, Decimal(0)) + used
    return totals


def json_number(dose):
    # В JSON дозировка должна быть числом. Расход уже посчитан через Decimal.
    return int(dose) if dose == int(dose) else float(dose)


def save_to_mysql(text, orders_json, user, host, port):
    try:
        import mysql.connector
    except ImportError:
        raise SystemExit('Для сохранения установи mysql-connector-python по инструкции в README.md')

    try:
        with mysql.connector.connect(user=user, password=getpass('Пароль MySQL: '),
                                     host=host, port=port, database='pharmacy_test') as db:
            with db.cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS chat_orders (
                    message_hash CHAR(64) PRIMARY KEY,
                    orders_json JSON NOT NULL
                ) ENGINE=InnoDB''')
                # Повторная загрузка того же текста обновляет ту же запись.
                message_hash = hashlib.sha256(text.strip().encode('utf-8')).hexdigest()
                cursor.execute('''INSERT INTO chat_orders (message_hash, orders_json) VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE orders_json = %s''', (message_hash, orders_json, orders_json))
                db.commit()
                cursor.execute('SELECT orders_json FROM chat_orders')
                saved_orders = []
                for (document,) in cursor:
                    saved_orders.extend(json.loads(document, parse_float=Decimal))
                return calculate_totals(saved_orders)
    except mysql.connector.Error as error:
        raise SystemExit(f'Ошибка MySQL: {error}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', nargs='?', type=Path, default=Path(__file__).with_name('orders.txt'))
    parser.add_argument('--save', action='store_true', help='сохранить в MySQL')
    parser.add_argument('--user', default='root', help='пользователь MySQL')
    parser.add_argument('--host', default='127.0.0.1', help='адрес MySQL')
    parser.add_argument('--port', default=3306, type=int, help='порт MySQL')
    args = parser.parse_args()

    try:
        text = args.file.read_text(encoding='utf-8-sig')
        orders = parse_orders(text)
        totals = calculate_totals(orders)
        orders_json = json.dumps(orders, ensure_ascii=False, indent=2, default=json_number)
        output = args.file.with_suffix('.json')
        if output.resolve() == args.file.resolve():
            raise ValueError('Укажи текстовый файл с расширением .txt')
        output.write_text(orders_json + '\n', encoding='utf-8')
    except (OSError, ValueError) as error:
        raise SystemExit(f'Ошибка: {error}')

    print(f'JSON: {output.name}')
    if args.save:
        totals = save_to_mysql(text, orders_json, args.user, args.host, args.port)
        print('Общий расход по сообщениям в MySQL:')
    for name, total in totals.items():
        print(f'{name}: {total:f} мг')


if __name__ == '__main__':
    main()
