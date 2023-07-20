import telebot
from telebot import types, apihelper
from telebot.handler_backends import ContinueHandling, CancelUpdate
import info
import sys
import os
import threading as th
import time, datetime
import shelve

# Create directories for journal files and message data.
import os
try:
    os.mkdir(r'./log/')
except FileExistsError:
    pass

try:
    os.mkdir(r'./data/')
except FileExistsError:
    pass

# Register a logger to see what the hell is going on (debug purpose).
import logging
from logging.handlers import TimedRotatingFileHandler
logger = telebot.logger
logger.setLevel(logging.INFO)

log_name = r'./log/bot_log_file.log'
log_format = logging.Formatter(
    '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s'
    )

log_handler = TimedRotatingFileHandler(log_name, when='D', interval=1, backupCount=5)
log_handler.setFormatter(log_format)
log_handler.setLevel(logging.INFO)
logger.addHandler(log_handler)

client = telebot.TeleBot(info.data['TOKEN']) # Creating instance of telebot

last_time = {}
# Simple antiflood handler
# This message handler is supposed to handle every message from any user.
# If user id isn't in a dict, add him and return instace of ContinueHandling class to continue handling the
# message. Otherwise, timestamps are compared.If not enough time has passed, function returns an
# instance of the CancelUpdate class to skip all below handlers.
@client.message_handler(func=lambda message:True)
def antiflood(message):
    limit=2
    if not message.from_user.id in last_time:
        last_time[message.from_user.id] = [message.date, message.media_group_id]
        return ContinueHandling()

    if message.date - last_time[message.from_user.id][0] < limit:
        if (message.media_group_id and last_time[message.from_user.id][1] == message.media_group_id):
            return ContinueHandling()

        last_time[message.from_user.id] = [message.date, message.media_group_id]
        client.send_message(message.chat.id, 'You are making request too often')
        return CancelUpdate()

    else:
        last_time[message.from_user.id] = [message.date, message.media_group_id]
        return ContinueHandling()
    
# Func call sends hello message, if admin id and channel id specified otherwise sends message, that
# you have to fill the file '"admin.conf".
@client.message_handler(commands = ['start'])
def start(message):
    if not is_admin_set():
        client.send_message(message.chat.id, f'''Необходимо заполнить файл "admin.conf". Для этого добавьте бота в канал по ссылке @{info.data["name"]}, а затем воспользутесь командой /set_channel.''')
        
    else:
        client.send_message(message.chat.id, '''Greetings traveler! Ты попал в бота преложки. Присылай свой пост.''')
        
# Decorator handles only photo, video and animation message.content_type, but you can specified you
# own (see telebot.util.content_type_media).
# Func saves message data in ./data/media_content file with unique key.
# For a media group, the key is a string consisting of the chat id and the media group id, separated
# by a vertical slash.
# The key of simple message consisting of the chat id and message id separated by a vertical slash.
@client.message_handler(content_types = ['photo','video','animation'], func=lambda message: is_admin_set())
def media_saver(message):
    media_content = shelve.open(r'./data/media_content')
    if message.media_group_id:
            uni_id = f'{message.chat.id}|{message.media_group_id}'
            if uni_id not in [*media_content.keys()]:
                media_content[uni_id] = {'username':message.chat.username,'is mg': True,'input media':[],'editing':False}

            if message.content_type == 'photo':
                temp = media_content[uni_id]
                temp['input media'].append(types.InputMedia(message.content_type,
                                                            message.photo[-1].file_id,
                                                            message.caption,
                                                            parse_mode = None,
                                                            caption_entities = message.caption_entities))
                media_content[uni_id] = temp

            elif message.content_type == 'video':
                temp = media_content[uni_id]
                temp['input media'].append(types.InputMedia(message.content_type,
                                                            message.video.file_id,
                                                            message.caption,
                                                            parse_mode = None,
                                                            caption_entities = message.caption_entities))
                media_content[uni_id] = temp


    else:
            uni_id = f'{message.chat.id}|{message.message_id}'

            if message.content_type == 'photo':
                media_content[uni_id] = {'username':message.chat.username,'is mg': False,'input media':[message.content_type,
                                          message.photo[-1].file_id,
                                          message.caption, message.caption_entities],'editing':False}

            elif message.content_type == 'video':
                media_content[uni_id] = {'username':message.chat.username,'is mg': False,'input media':[message.content_type,
                                          message.video.file_id,
                                          message.caption, message.caption_entities],'editing':False}

            elif message.content_type == 'animation':
                media_content[uni_id] = {'username':message.chat.username,'is mg': False,'input media':[message.content_type,
                                          message.document.file_id,
                                          message.caption, message.caption_entities],'editing':False}

    media_content.close()
    logger.info(f'Saved: {uni_id}')

# Func call cleans key(uni_id)-specified data.
def media_cleaner(uni_id):
    with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
        if uni_id in [*scheduled_messages.keys()]:
            del scheduled_messages[uni_id]

    with shelve.open(r'./data/bot_msg') as bot_msg:
        if uni_id in [*bot_msg.keys()]:
            del bot_msg[uni_id]

    with shelve.open(r'./data/media_content') as media_content:
        if uni_id in [*media_content.keys()]:
            del media_content[uni_id]

    logger.info(f'Cleaned: {uni_id}')

# Func call sends stored (media group/message) specified by uni_id.
def media_sender(uni_id, chat_id, state=None):
    media_content = shelve.open(r'./data/media_content')
    bot_msg = shelve.open(r'./data/bot_msg')
    if media_content[uni_id]['is mg']:

        bot_media_group = client.send_media_group(chat_id, media_content[uni_id]['input media'])
        bot_msg[uni_id] = bot_media_group[0]

    elif media_content[uni_id]['is mg'] == False:

        if media_content[uni_id]['input media'][0] == 'photo':
            bot_msg[uni_id] = client.send_photo(chat_id,
                              media_content[uni_id]['input media'][1],
                              media_content[uni_id]['input media'][2],
                              caption_entities = media_content[uni_id]['input media'][3])

        elif media_content[uni_id]['input media'][0] == 'video':
            bot_msg[uni_id] = client.send_video(chat_id,
                              media_content[uni_id]['input media'][1],
                              media_content[uni_id]['input media'][2],
                              caption_entities = media_content[uni_id]['input media'][3])

        elif media_content[uni_id]['input media'][0] == 'animation':
            bot_msg[uni_id] = client.send_animation(chat_id,
                                media_content[uni_id]['input media'][1],
                                caption = media_content[uni_id]['input media'][2],
                                caption_entities = media_content[uni_id]['input media'][3])

    else:
        logger.info(f'Missing: {uni_id}')

    media_content.close()
    bot_msg.close()
    
    if state == 'approve':
        media_cleaner(uni_id)

# Func calls in the listener func after saving message media data and creates uni_id.
# uni_id is identifier I use all the way through callback functions
# Every inline button has callback data consisting of call_state which required for handling call correctly
# and uni_id which using as a key to access message data stored in files.
def end_of_handling(message, uni_id):
    media_sender(uni_id, message[0].chat.id)###
    logger.info(f'End of handling: {uni_id}')
    return usr_ans(message[0], uni_id)

# Func call raises inline button menu in user chat to confim or reject sending the message to admin.
def usr_ans(message, uni_id):

    keyboard = types.InlineKeyboardMarkup()

    send_button = types.InlineKeyboardButton('Отправить',
                                                     callback_data=f'send, {uni_id}'
                                                     )
    cancel_button = types.InlineKeyboardButton(text='Отмена',
                                                     callback_data=f'cancel, {uni_id}'
                                                     )
    keyboard.add(send_button, cancel_button)

    client.send_message(message.chat.id, 'Подтвердите отправку.',
                                reply_markup=keyboard
                                )

# Func call raises inline buttons menu in admin chat to publish sended message in the channel specified
# in admin.conf file or reject it.
# Also there are 2 button to edit message caption and to set the date of pubslishing it in the channel.
@client.callback_query_handler(func = lambda call: call.data.startswith(('send','cancel','edit_done', 'sch_done', 'sch_cancel')))
def admin_ans(call):
    call_state, uni_id = call.data.split(', ')
    if not is_button_alive(uni_id, call):
        return
    with shelve.open(r'./data/media_content') as media_content:
        username = media_content[uni_id]['username']

    if call_state in ['send', 'edit_done', 'sch_done', 'sch_cancel']:

        keyboard = types.InlineKeyboardMarkup()
        approve_button = types.InlineKeyboardButton('Принять',
                                                    callback_data = f'approve, {uni_id}'
                                                    )
        reject_button = types.InlineKeyboardButton('Отклонить',
                                                   callback_data = f'reject, {uni_id}'
                                                   )
        edit_button = types.InlineKeyboardButton('Редактировать текст',
                                                 callback_data = f'edit, {uni_id}'
                                                 )
        schedule_button = types.InlineKeyboardButton('Установить время публикации',
                                                 callback_data = f'schedule, {uni_id}'
                                                 )

        keyboard.add(approve_button, reject_button, edit_button, schedule_button)
        if call_state == 'sch_cancel':
            with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
                if uni_id in [*scheduled_messages.keys()]:
                    del scheduled_messages[uni_id]

            client.edit_message_text(f'''Пользователь @{username} предложил новый пост.\nID:{uni_id}''',
                                     call.message.chat.id,
                                     call.message.message_id,
                                     reply_markup=keyboard
                                     )

        elif call_state == 'sch_done':
            with shelve.open(r'./data/media_content') as media_content:
                temp = media_content[uni_id]
                temp['editing'] = False#set editing status False
                media_content[uni_id] = temp

            with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
                if uni_id in [*scheduled_messages.keys()]:
                    client.edit_message_text(f'''Сообщение пользователя @{username} будет опубликовано {scheduled_messages[uni_id]['publish date']}.\nID:{uni_id}''',
                                         call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=keyboard
                                         )
                else:
                    client.edit_message_text(f'''Пользователь @{username} предложил новый пост.\nID:{uni_id}''',
                                         call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=keyboard
                                         )

        elif call_state == 'edit_done':
            with shelve.open(r'./data/media_content') as media_content:
                temp = media_content[uni_id]
                temp['editing'] = False#set editing status False
                media_content[uni_id] = temp

            client.edit_message_text(f'''Пользователь @{username} предложил новый пост.\nID:{uni_id}''',
                                        call.message.chat.id,
                                        call.message.message_id,
                                        reply_markup=keyboard
                                        )

        elif call_state == 'send':
            client.edit_message_reply_markup(call.message.chat.id,
                                     call.message.message_id,
                                     reply_markup=None
                                     )
            with shelve.open('admin.conf') as cf:
                media_sender(uni_id, cf['admin_id'], call_state)
                client.send_message(cf['admin_id'],
                                f'''Пользователь @{username} предложил новый пост.\nID:{uni_id}''',
                                reply_markup=keyboard
                                )

    elif call_state == 'cancel':
        client.edit_message_text('''Отправка отменена.''',
                                     call.message.chat.id,
                                     call.message.message_id,
                                     reply_markup=None
                                     )

        media_cleaner(uni_id)

# This callback handler handles edit button callback query.
@client.callback_query_handler(func = lambda call: call.data.startswith('edit'))
def edit(call):
    call_state, uni_id = call.data.split(', ')

    if (not is_button_alive(uni_id, call) or is_any_editing()):#check if any message is already editing
        return

    with shelve.open(r'./data/media_content') as media_content:#set editing status True
        temp = media_content[uni_id]
        temp['editing'] = True
        media_content[uni_id] = temp

    client.edit_message_text('Введите новый текст.',
                             call.message.chat.id,
                             call.message.message_id,
                             reply_markup=None
                             )

    client.register_next_step_handler_by_chat_id(call.message.chat.id, editor, uni_id, call)

# Func firstly check, if sended message.content_type is text. If it's true, func edits message caption
# stored in /data/media_content file and also if everything goes rigth edits caption of message linked
# with uni_id in admin's chat.
def editor(message, uni_id, call):
    client.delete_message(message.chat.id, message.message_id)

    if message.content_type == 'text':
        new_caption = message.text
        new_enteties = message.entities

        keyboard = types.InlineKeyboardMarkup()

        done_button = types.InlineKeyboardButton('Готово',
                                                        callback_data=f'edit_done, {uni_id}'
                                                        )
        keyboard.add(done_button)

        client.edit_message_reply_markup(call.message.chat.id,
                                     call.message.message_id,
                                     reply_markup=keyboard
                                     )

        with shelve.open(r'./data/bot_msg') as bot_msg:
            client.edit_message_caption(new_caption,
                                        message.chat.id,
                                        bot_msg[uni_id].message_id,
                                        caption_entities = new_enteties
                                        )
            
        with shelve.open(r'./data/media_content') as media_content:
            if media_content[uni_id]['is mg']:
                mc_dict = media_content[uni_id]['input media'][0].to_dict()
                temp = media_content[uni_id]
                temp['input media'][0] = types.InputMedia(mc_dict['type'],
                                                                     mc_dict['media'], new_caption,
                                                                     parse_mode=None, caption_entities=new_enteties)
                media_content[uni_id] = temp

            else:
                temp = media_content[uni_id]
                temp['input media'][2] = new_caption
                temp['input media'][3] = new_enteties
                media_content[uni_id] = temp
                
    else:
        client.register_next_step_handler_by_chat_id(message.chat.id, editor, uni_id, call)

# The function checks if the message is approved. If yes, then checks if it is scheduled.
# If no publication date is specified, the message is published immediately.
# After publishing the message, all data belonging to specifiedd uni_id will be cleaned.
# Also function sends feedback to user who proposed publication.
@client.callback_query_handler(func = lambda call: call.data.startswith(('approve', 'reject')))
def approve(call):
    call_state, uni_id = call.data.split(', ')
    senders_chat, msg_id = uni_id.split('|')

    if not is_button_alive(uni_id, call):
        return

    if call_state == 'approve':
        client.send_message(senders_chat, '''Пост одобрен администратором.''')

        with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
            if uni_id not in [*scheduled_messages.keys()]:# if the message scheduled
                client.edit_message_reply_markup(call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=None
                                         )
                with shelve.open('admin.conf') as cf:
                    media_sender(uni_id, cf['channel_id'], call_state)

            else:
                keyboard = types.InlineKeyboardMarkup()
                cancel_button = types.InlineKeyboardButton('Отмена',
                                                        callback_data=f'sch_cancel, {uni_id}'
                                                        )
                keyboard.add(cancel_button)
                client.edit_message_reply_markup(call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=keyboard
                                         )

    elif call_state == 'reject':
        client.send_message(senders_chat, '''Пост отклонен''')

        client.edit_message_reply_markup(call.message.chat.id,
                                     call.message.message_id,
                                     reply_markup=None
                                     )
        media_cleaner(uni_id)
        
# This callback handler handles schedule button callback query.
@client.callback_query_handler(func = lambda call: call.data.startswith('schedule'))
def msg_schedule(call):
    call_state, uni_id = call.data.split(', ')
    if (not is_button_alive(uni_id, call) or is_any_editing()):#check if any message is already editing
        return

    with shelve.open(r'./data/media_content') as media_content:#set editing status True
        temp = media_content[uni_id]
        temp['editing'] = True
        media_content[uni_id] = temp

    with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
        if uni_id in [*scheduled_messages.keys()]:
            del scheduled_messages[uni_id]

    client.edit_message_text(f'''Введите дату и время в формате "{datetime.datetime.now().strftime('%Y:%m:%d:%H:%M')}".''', call.message.chat.id, call.message.message_id, reply_markup=None)

    client.register_next_step_handler_by_chat_id(call.message.chat.id, scheduler, uni_id, call)

# The function firstly checks if it is a text message, then tries to obtain the date, checks if the date is valid.
# If so, it saves the date in the schedule_messages file and creates a button to return to the main menu.
def scheduler(message, uni_id, call):
    client.delete_message(message.chat.id, message.message_id)

    if message.content_type == 'text':
        msg_text = message.text

        try:
            year, month, day, hour, minute = msg_text.split(':')
            date = datetime.datetime(int(year), int(month), int(day), int(hour), int(minute), 0)
            unix_date = datetime.datetime.timestamp(date)

        except:
            client.register_next_step_handler_by_chat_id(message.chat.id, scheduler, uni_id, call)

        else:
            delta = unix_date - int(message.date)
            if delta<0:
                client.register_next_step_handler_by_chat_id(message.chat.id, scheduler, uni_id, call)
            else:
                with shelve.open(r'./data/scheduled_messages') as scheduled_messages:
                    scheduled_messages[uni_id] = {'unix': int(unix_date), 'publish date': f'{day}/{month}/{year} {hour}:{minute}'}

                keyboard = types.InlineKeyboardMarkup()

                done_button = types.InlineKeyboardButton('Готово', callback_data=f'sch_done, {uni_id}')
                keyboard.add(done_button)
                client.edit_message_text(f'''Время публикации {day}/{month}/{year} {hour}:{minute}. ID:{uni_id}''',
                                         call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=keyboard
                                         )

    else:
        client.register_next_step_handler_by_chat_id(message.chat.id, scheduler, uni_id, call)

# Function to be called whenever new message arrives.
# It helps to handle media groups. Listener func receives the entire media group as a list of messages,
# while message_handler receives each media group message separately.
# Also I use sleep() method, so that the media_saver func has time to process all messages.
def listener(message):
    if not message:
        return
    if not is_admin_set:
        return
    time.sleep(1)
    if len(message)>1:
        uni_id = f'{message[0].chat.id}|{message[0].media_group_id}'

    else:
        uni_id = f'{message[0].chat.id}|{message[0].message_id}'

    media_content = shelve.open(r'./data/media_content')
    if uni_id in [*media_content.keys()]:
        media_content.close()
        end_of_handling(message, uni_id)
        
    media_content.close()
    
client.set_update_listener(listener)

# Function call use to set admin id and channel id in admin.conf file.
# First you enter a command and then the bot asks you to send any post from the channel.
@client.message_handler(commands = ['set_channel'])
def set_channel(message):
    with shelve.open('admin.conf') as cf:
        if 'lock' in [*cf.keys()] and cf['lock']:
            client.send_message(message.chat.id, '''Locked. Type /lock command to change admin id and channel id.''')
        else:
            client.send_message(message.chat.id, '''Для инициализации необходимо переслать любой пост из вашего телеграм канала.''')
            client.register_next_step_handler(message, conf_parser)

def conf_parser(message):
    if message.forward_from_chat != None and message.forward_from_chat.type == 'channel':
        with shelve.open('admin.conf') as cf:
            cf['admin_id'] = f'{message.chat.id}'
            cf['channel_id'] = f'{message.forward_from_chat.id}'
            cf['lock'] = True
        client.send_message(message.chat.id,
                            f'''Channel has been set successfully.\nAdmin chat ID = {message.chat.id}, Channel {message.forward_from_chat.title} chat ID = {message.forward_from_chat.id}.\n\nLock = True.'''
                            )

    else:
        client.send_message(message.chat.id, '''Chat type is not channel. Try again.''')
# Function call locks and unlocks file admin.conf by editing the 'lock' field
@client.message_handler(commands = ['lock'])        
def lock(message):
    with shelve.open('admin.conf') as cf:
        if 'lock' in [*cf.keys()] and f'{message.chat.id}' == cf['admin_id']:
            if cf['lock']:
                client.send_message(message.chat.id, '''Unlocked.''')
            else:
                client.send_message(message.chat.id, '''Locked.''')
            cf['lock'] = not cf['lock']
        elif not 'lock' in [*cf.keys()]:
            client.send_message(message.chat.id, '''Need to configure admin.conf.''')
        else:
            client.send_message(message.chat.id, '''No privileges.''')

# Re handler to handle non-existing commands
@client.message_handler(regexp = r"^/.+")
def unsupported(message):
    client.send_message(message.chat.id, "Unsupported command.")
    
# Function is called to check if the admin.conf file is filled.
def is_admin_set():
    is_set = True
    with shelve.open('admin.conf') as cf:
        if not [*cf.keys()]:
            is_set=False
            logger.warning('admin.conf file is empty')
    return is_set

# Function call clears old buttons.
# Function returns True if file(media_content) has key(uni_id)-specified data.
def is_button_alive(uni_id, call):
    is_alive = True
    with shelve.open(r'./data/media_content') as media_content:
        if uni_id not in [*media_content.keys()]:
            client.edit_message_reply_markup(call.message.chat.id,
                                         call.message.message_id,
                                         reply_markup=None
                                         )
            is_alive = False
            logger.warning('Button is out of date')

    return is_alive

# Function check every minute, if it's time to send scheduled message.
# pyTelegramBotAPI library does't have any method like send_scheduled_message or kinda like that,
# so using threading library is how I see the solution.
# At the start of executing program create thread object. Thread calls function with infinity loop to check
# scheduled_messages file every iteration. When it is the time, thread calls media_sender function.
# Thread will run until internal flag is set to true.
def bot_backgroud_monitor(event, cycle):
    while True:
        if event.is_set():
            break
        time.sleep(60)
        cycle += 1
        logger.info(f'Bot is runnig {cycle} min')
        with shelve.open('admin.conf') as cf:
            scheduled_messages = shelve.open(r'./data/scheduled_messages')
            temp = scheduled_messages
            keys = [*temp.keys()]
            scheduled_messages.close()
            if keys:
                for key in keys:
                    if temp[key]['unix']-int(time.time())<0:
                        media_sender(key,cf['channel_id'], 'approve')


# Function call check if admin alredy editing any other message.
# If function returns True, admin can't reach either message caption edit method or message schedule
# method.
def is_any_editing():
    is_editing = False
    with shelve.open(r'./data/media_content') as media_content:
        for key in [*media_content.keys()]:
            if media_content[key]['editing']:
                is_editing = True

    logger.info(f'Message is already editing {is_editing}')
    return is_editing

if __name__ == "__main__":
    try:
        cycle = 0
        event = th.Event()
        thread = th.Thread(target=bot_backgroud_monitor, name='Monitor', args=(event,cycle,))
        thread.start() # start background thread
        #apihelper.RETRY_ON_ERROR = True
        apihelper.RETRY_TIMEOUT = 10
        apihelper.MAX_RETRIES = float('inf')
        client.polling(non_stop = True, skip_pending = True)
    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        logger.error(e)
        pass
    finally:
        event.set()
        thread.join() # waiting until thread terminates
        logger.info(f'Background thread is alive: {thread.is_alive()}')
