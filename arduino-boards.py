
import sys
import os
import json
import PySimpleGUI as sg
from shutil import copyfile
import copy

# C:\Users\timkay\AppData\Local\Arduino15

# c:/Users/timkay/AppData/Local/Arduino15/packages/arduino/hardware/avr/1.8.2/boards.txt
# c:/Users/timkay/AppData/Local/Arduino15/packages/arduino/hardware/samd/1.8.5/boards.txt
# c:/Users/timkay/AppData/Local/Arduino15/packages/STM32/hardware/stm32/1.8.0/boards.txt


def scan(dir):
    dir = dir.replace('\\', '/')
    names = []
    try:
        with os.scandir(dir) as it:
            for file in it:
                names.append(file.name)
    except IOError:
        pass
    return names


def load_boards(board_path):

    data = {}

    if not os.path.exists(board_path):
        return data

    with open(board_path, encoding='utf-8', mode='r') as fi:
        while True:
            line = fi.readline()
            if not line:
                break
            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue;
            path, value = line.split('=', 1)
            *parts, key = path.split('.')
            dp = data
            for part in parts:
                if part not in dp:
                    dp[part] = {}
                if isinstance(dp[part], str):
                    dp[part] = {'*name': dp[part]}
                dp = dp[part]
            if key in dp:
                #print('duplicate key', line)
                pass
            else:
                dp[key] = value

    return data


def maybe_copy_boards_txt(boards_txt):
    # copy boards.txt to boards.txt.mastr
    orig = boards_txt + '.mastr'
    if os.path.exists(boards_txt) and not os.path.exists(orig):
        window['OUTPUT'].print('creating', orig)
        copyfile(boards_txt, orig)


def find_boards_txts(root):
    boards_txts = []
    packages_dir = root + '/packages'
    for package in scan(packages_dir):
        try:
            package_dir = packages_dir + '/' + package + '/hardware'
            for arch in scan(package_dir):
                arch_dir = package_dir + '/' + arch
                for ver in scan(arch_dir):
                    ver_dir = arch_dir + '/' + ver
                    boards_txt = ver_dir + '/' + 'boards.txt'
                    if os.path.exists(boards_txt):
                        boards_txts.append(boards_txt)
        except IOError:
            pass
    return boards_txts

# Load boards.txt (primary=True) or boards.txt.mastr (primary=False)
def load_boards_txts(root, primary=False, update=False):
    if primary and update:
        # don't do this
        return
    reminder = False
    boards_list = []
    for boards_txt in find_boards_txts(root):
        maybe_copy_boards_txt(boards_txt)
        if primary:
            data = load_boards(boards_txt)
        else:
            data = load_boards(boards_txt + '.mastr')
        section_count = 0
        newfile = boards_txt + '.new'

        with open(newfile, 'w') as fo:
            if 'menu' in data:
                for key in data['menu']:
                    fo.write('menu.%s=%s\n' % (key, data['menu'][key]));
            for key in data:
                if key == 'menu':
                    continue
                many = None
                if 'menu' in data[key]:
                    for choice in data[key]['menu']:
                        for item in data[key]['menu'][choice]:
                            if 'build' in data[key]['menu'][choice][item]:
                                if 'board' in data[key]['menu'][choice][item]['build']:
                                    many = choice
                                    boards_list.append([
                                        'x',
                                        ' '.join([
                                            data[key]['name'],
                                            data[key]['menu'][choice][item]['*name'],
                                        ]),
                                        boards_txt.replace(root, '...'),
                                    ])
                if many:
                    menu = data[key]['menu'][many]
                    del data[key]['menu'][many]
                    for item in menu:
                        newkey = '_'.join([key, item])
                        newname = ' '.join([data[key]['name'], menu[item]['*name']])
                        if included.get(newname):
                            node = merge(data[key], menu[item])
                            node['name'] = newname
                            section = make_build_line(newkey, node)
                            fo.write('\n' + section)
                            section_count += 1
                        
                else:
                    if 'name' in data[key]:
                        boards_list.append([
                            'x',
                            data[key]['name'],
                            boards_txt.replace(root, '...'),
                        ])
                        if included.get(data[key]['name']):
                            section = make_build_line(key, data[key])
                            fo.write('\n' + section)
                            section_count += 1
            if section_count == 0:
                fo.write('\nNoBoard.name=(No boards selected)\nNoBoard.build.board=NOBOARD\n')
        if update: # and os.stat(newfile).st_size > 100:
            dest = None
            orig = None
            with open(boards_txt) as fi:
                dest = fi.read()
                with open(newfile) as fi:
                    orig = fi.read()
                    if dest != orig:
                        copyfile(newfile, boards_txt)
                        window['OUTPUT'].print('updated:', boards_txt)
                        reminder = True

    boards_list.sort(key=lambda x: x[1].lower())
    boards_list.sort(key=lambda x: x[2].lower())

    if reminder:
        window['OUTPUT'].print('RESTART THE ARDUINO IDE TO TAKE AFFECT')

    return boards_list


def merge(adict, bdict):
    def merge_r(adict, bdict):
        for b in bdict:
            if type(bdict[b]) != dict:
                adict[b] = bdict[b]
            elif b not in adict:
                adict[b] = bdict[b]
            else:
                merge_r(adict[b], bdict[b])
    node = copy.deepcopy(adict)
    merge_r(node, bdict)
    return node
            

def make_build_line(s, dict):
    lines = []
    def emit(line):
        lines.append(line)
    def make_build_line_r(s, dict):
        for key in dict:
            if type(dict[key]) == str:
                if key == '*name':
                    emit(s + '=' + dict[key])
                else:
                    emit(s + '.' + key + '=' + dict[key])
            else:
                make_build_line_r(s + '.' + key, dict[key])
    #print('make_build_line', s, json.dumps(dict, indent=4))
    make_build_line_r(s, dict)
    lines.append('')
    return '\n'.join(lines)


def find_arduino_dir():
    cwd = os.getcwd()
    #cwd = '/home/$USER/.arduino15/';
    #cwd = '/Users/$USER/Library/Arduino15/';
    cwd = '/'.join(cwd.replace('\\', '/').split('/')[0:3])
    for path in ['.arduino15', 'Library/Arduino15', 'AppData/Local/Arduino15']:
        arduino_dir = cwd + '/' + path
        if os.path.exists(arduino_dir):
            window['OUTPUT'].print('Found', arduino_dir)
            return arduino_dir
        else:
            #window['OUTPUT'].print('trying', arduino_dir)
            pass
    return ''



settings_file = 'settings.txt'
app_title = 'Arduino Boards Tuner'

checked   = ' ☑'
unchecked = ' ☐'

output = None
included = {}
window = None
data = []


if False:
    collapse()

else:
    layout = [
        [sg.Text(app_title, key='TITLE')],
        [sg.Text('Arduino packages directory:'), sg.Input(key='DIR'), sg.Button('Refresh')],
        [sg.Button('None'), sg.Button('All'), sg.Button('Close')],
        [sg.Text('Choose which boards are visible in the Arduino IDE. Double click to (un)check.')],
        [sg.Table(
            num_rows=30,
            headings=['Use', 'Board', 'boards.txt path'],
            values=data,
            auto_size_columns=False, 
            col_widths=[5, 60, 70],
            justification='left',
            #select_mode=Select Mode. Valid values start with "TABLE_SELECT_MODE_".  Valid values are: TABLE_SELECT_MODE_NONE TABLE_SELECT_MODE_BROWSE TABLE_SELECT_MODE_EXTENDED
            font=('Courier', 8),
            key='TABLE',
            #enable_events=True,
            #change_submits=True,
            bind_return_key=True,
        )],
        [sg.Multiline(size=(139,10), font=('Courier', 8), key='OUTPUT')],
    ]
    #layout.append([sg.Checkbox('Checkbox 1')])
    #layout.append([sg.Checkbox('Checkbox 2')])

    window = sg.Window(app_title, layout) #, return_keyboard_events=True)
    window.finalize()

    root = find_arduino_dir()
    window['DIR'].update(root or '(not set)')

    # load live file to see what's been selected
    for board in load_boards_txts(root, primary=True):
        included[board[1]] = True

    data = load_boards_txts(root)
    for row in data:
        row[0] = checked if included.get(row[1]) else unchecked
    window['TABLE'].update(data)

    if output is not None:
        window['OUTPUT'].print(output)

    while True:
        event, values = window.read()
        if event in (None, 'Close'):
            break
        if event in ('Refresh'):
            if os.path.exists(values.get('DIR', '') + '/packages'):
                load_boards()
            else:
                window['OUTPUT'].print('Arduino directory is wrong')
            continue
        if event in ('None', 'All'):
            for row in data:
                row[0] = unchecked if event == 'None' else checked
            window['OUTPUT'].print('updating table')
            window['TABLE'].update(data)
            continue
        if event == 'TABLE':
            row = data[values['TABLE'][0]]
            key = row[1]
            if included.get(key):
                del included[key]
                row[0] = unchecked
            else:
                included[key] = True
                row[0] = checked
            window['OUTPUT'].print('Including', key, included.get(key, False))
            load_boards_txts(root, update=True)
            window['TABLE'].update(data)

    window.close()

