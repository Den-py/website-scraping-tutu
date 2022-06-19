import sys
import requests
import datetime
from bs4 import BeautifulSoup
import lxml


def main():
    """
    Скрипт принимает три аргумента:
        Первый аргумент - дата отправления. Этот аргумент является обязательным. Записывается в формате DD.MM.YYYY

        Второй и третий аргументы - названия станций отправления и прибытия. Оба являются не обязательными параметрами.
        В случае, если в параметре нужно указать название состоящие из нескольких слов, следует записать его
        через нижнее подчеркивание.
        Пример: Ленинский_Проспект
    """

    arguments = sys.argv

    # удаление не используемого параметра
    del arguments[0]

    # проверка на наличие времени отбытия
    if arguments:

        # Заполнение названиями станций значениями по умолчанию в случае, если пользователь их не указал 
        if len(arguments) == 1:
            arguments.append("Санкт-Петербург")
        if len(arguments) == 2:
            arguments.append("Сусанино")

        st_name = arguments.pop(1)
        arguments.insert(1, st_name.replace('_', ' '))
        st_name = arguments.pop(2)
        arguments.insert(2, st_name.replace('_', ' '))

        # функция посылает запрос на сайт, а полученный ответ записывает в переменную
        main_html = parsing(arguments)
        if main_html is not None:
            soup = BeautifulSoup(main_html.text, 'lxml')
            # Проверка корректности названий введённых станций
            if errors_checking(main_html, soup):
                train_searching(soup)
        else:
            print("Получен некорректный html.")
    else:
        print("Вы не указали дату отправления.")

    return 0


def parsing(search_arguments):
    """
    Функция посылает запрос на сайт www.tutu.ru, и возвращает полученный ответ.
    В случае проблем выводит сообщение об ошибки.

    :param search_arguments: список в котором содержатся параметры запроса.
    :return: содержимое страницы или None, в случае если при отправке запроса произошли какие-либо сбои.

    """
    arg_dict = dict(st1=search_arguments[1],
                    st2=search_arguments[2],
                    date=search_arguments[0],
                    button='clicked1')
    try:
        html = requests.get('https://www.tutu.ru/prigorod/search.php', params=arg_dict)
        if 200 <= html.status_code <= 399:
            return html
        else:
            print('[' + str(html.status_code) + '] - ошибка клиента или сервера.')
            return None

    except requests.ConnectionError:
        print('Сайта не существует или проблемы с интернет соединением.')
        return None


def errors_checking(html, soup):
    """
    Функция обрабатывает различные сценарии приводящие к некорректной работе программы.

    :param html: содержимое страницы, с которым в дальнейшем предстоит работать.
    :param soup: содержимое страницы преобразованное для работы библиотекой bs4.
    :return: если все проверки пройдены, то возвращается True, иначе - False.

    """

    # Проверка корректности даты
    if str(html.url)[-3:] == 'all':
        print('Дата отправления была введена не корректно.')
        return False

    # Проверка на указания одного названия для станций отправления и прибытия
    if html.url.find('nnst=') != -1:
        print('Для отправки и отбытия вы указали одну и туже станцию.')
        return False

    # Проверка на наличие случаев, когда возникают ошибки, которые уже обработал сайт.
    # Например: Слишком короткое имя станции, отсутствие станции, отсутствие
    # маршрута, несколько станции под один запрос.
    massage_div = soup.find_all('div', attrs={'class': 'stationSelect'})
    if massage_div:
        massage = massage_div[0].find_all('p')
        if massage:
            print_text = massage[0].text.split('.')
            print(print_text[0]+".")
            return False

        # Вывод перечня станций, которые походят под запрашиваемое с просьбой задать более конкретное название.
        print('Пожалуйста уточните станции и запустите скрипт с более конкретными названиями.')
        clarification_of_the_station(massage_div, 'Left')
        clarification_of_the_station(massage_div, 'Right')

        return False
    # Проверяет, если сообщение об ошибке
    massage_div = soup.find_all('div', attrs={'class': 'warning_ico'})
    if massage_div:
        print(massage_div[0].text)
        return False
    return True


def clarification_of_the_station(massage_div, mod):
    """
    Функция перебирает и демонстрирует все возможные варианты
    пункта отправления(mod == 'Left') или прибытия(mod == 'Right').

    :param massage_div: часть сайта, внутри которого содержится список названий станций
                        удовлетворяющих запросу пользователя.
    :param mod: параметр определяющий какой список рассматриваем: отправления или отбытия.

    """
    if mod == 'Right':
        print('Пункт прибытия:')
        div_class = {'class': 'stationSelectRight'}
    elif mod == 'Left':
        print('Пункт отправления:')
        div_class = {'class': 'stationSelectLeft'}

    massage = massage_div[0].find_all('div', attrs=div_class)
    lables = massage[0].find_all('label')
    spans = massage[0].find_all('span', attrs={'class': 'small'})
    for i in range(len(lables)):
        # Получение названия станции без уточнения направления.
        station = str(lables[i].text.replace(spans[i].text, ""))
        print("\t", station, " (", spans[i].text, ")")


def train_searching(soup):
    """
    Функция находит время ближайшего электропоезда.

    :param soup: содержимое сайта, которое будет анализироваться.

    """
    now_time = datetime.datetime.now()
    table = soup.find_all('div', attrs={'id': 'timetable'})

    # Удовлетворение этому условию говорит о том, что маршрут с пересадкой.
    # При таком исходе, сайт имеет другую структуру и необходимо искать другой тег с другим id.
    if not table:
        table = soup.find_all('table', attrs={'id': 'schedule_table'})
        table = table[0].find_all('tbody')

    # Находим все теги a. Именно в них содержится время отправления.
    table_a = table[0].find_all('a')

    # Получаем href для последующей проверки на даты.
    search_date = str(table_a[0].get('href'))
    str_date = str(now_time.day) + "." + str(now_time.month) + "." + str(now_time.year)

    if (search_date.find(str_date) == -1) and (search_date.find('date=') != -1):
        search_date = datetime.datetime.strptime(search_date[-10:], '%d.%m.%Y')
        if search_date.date() < now_time.date():
            print("Подходящего электропоезда нет, так как указанный день уже закончился.")
            return
        else:
            print("Подходящий электропоезд отправляется в ", table_a[0].text)
            return
    else:
        for i in range(0, len(table_a), 4):
            departure_time = datetime.datetime.strptime(table_a[i].text, '%H:%M')
            if now_time.time() < departure_time.time():
                print("Подходящий электропоезд отправляется в ", table_a[i].text, " .")
                return


if __name__ == "__main__":
    main()

