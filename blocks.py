import logging

logger = logging.getLogger(__name__)


class Command:
    """
    Commandlet fabric class. Use as decorator for Mode methods.
    """

    number_free = 0
    number_used = set()

    def __init__(self, description='', command=None, number=None):
        self.description = description
        self.command = command
        self.number = self.set_number(number)

    def __call__(self, func):
        description = self.description
        command = self.get_command(func)
        number = self.number

        new_commandlet = Commandlet(description, command, number, func)
        return new_commandlet

    @classmethod
    def set_number(cls, number):
        if number is None:
            num = cls.number_free
            cls.number_free += 1
        else:
            num = int(number)

        while True:
            if num in cls.number_used:
                num += 1
            else:
                break
        return num

    def get_command(self, func):
        if self.command is None:
            return func.__name__
        else:
            return self.command


class Commandlet:
    command_width = 0
    arguments_width = 0

    def __init__(self, description, command, number, func):
        self.description = description
        self.command = command
        self.number = number
        self.func = func
        self.func_help = func.__doc__

        arguments = []
        for num, arg in enumerate(func.__code__.co_varnames):
            if num < func.__code__.co_argcount:
                arguments.append(arg)

        self.arguments = tuple(arguments)
        self.arguments_usage = ' '.join(['[%s]' % arg for arg in arguments[1:]])  # skip 'self'
        self.arguments_help = func.__annotations__
        self.arguments_max = len(self.arguments)

        if self.func.__defaults__ is None:
            self.arguments_min = self.arguments_max
        else:
            self.arguments_min = self.arguments_max - len(self.func.__defaults__)

        arguments_width = len(self.arguments_usage)
        if Commandlet.arguments_width < arguments_width:
            Commandlet.arguments_width = arguments_width

        command_width = len(command)
        if Commandlet.command_width < command_width:
            Commandlet.command_width = command_width

    @property
    def short_help(self):
        return '\t%s    %s    %s' % (self.command.ljust(self.command_width),
                                     self.arguments_usage.ljust(self.arguments_width), self.description)

    @property
    def long_help(self):
        lines = ['Name:']
        if self.description:
            lines.append('\t%s - %s' % (self.command, self.description))
        else:
            lines.append(self.command)
        lines.append('')
        lines.append('Usage:')
        lines.append('\t%s %s' % (self.command, self.arguments_usage))

        if self.arguments_help:
            lines.append('')
            lines.append('Arguments:')

            arg_width = 0
            arg_lines = []
            for arg_name in self.arguments[1:]:  # skip 'self'
                try:
                    arg_help = self.arguments_help[arg_name]
                except KeyError:
                    continue
                else:
                    if arg_width < len(arg_name):
                        arg_width = len(arg_name)
                    arg_lines.append((arg_name, arg_help))

            for arg in arg_lines:
                lines.append('\t%s - %s' % (arg[0].ljust(arg_width), arg[1]))

        if self.func_help:
            lines.append('')
            lines.append('Description:')
            func_help_lines = [i.strip() for i in self.func_help.strip().split('\n')]
            lines.append('\t' + '\n\t'.join(func_help_lines))

        return '\n'.join(lines)

    def __call__(self, *args, **kwargs):
        arguments_passed = len(args) + len(kwargs)

        if arguments_passed > self.arguments_max:
            raise IncorrectArguments('exceeded maximum number of arguments')

        elif arguments_passed < self.arguments_min:
            raise IncorrectArguments('not enough arguments')

        else:
            for name in kwargs.keys():
                if name not in self.arguments:
                    raise IncorrectArguments('wrong keyword argument: %s' % name)

            return self.func(*args, **kwargs)

    def __repr__(self):
        return 'Command(%s)' % self.command

    def __hash__(self):
        return hash(self.command)

    def __eq__(self, other):
        return self.command == other.command


class Mode:
    def __call__(self):
        self.build_namespace()

        while True:
            command_name, arguments = self.get_user_input()
            try:
                command = self.lookup_command(command_name)
                logger.debug('calling command: %s, arguments: %s' % (command.command, arguments))
                command(self, *arguments)
            except IncorrectCommand as e:
                print('Incorrect command: %s' % e.msg)
            except IncorrectArguments as e:
                print('Incorrect arguments passed: %s' % e.msg)
            except StopIteration:
                break

    def build_namespace(self):
        namespace = []

        def get_commandlets(cls):
            for key, value in cls.__dict__.items():
                if isinstance(value, Commandlet):
                    if value not in namespace:
                        namespace.append(value)
            for base in cls.__bases__:
                get_commandlets(base)

        get_commandlets(self.__class__)

        self.namespace = namespace

    def get_user_input(self):
        name = self.__dict__.get('name', 'unnamed')
        context = self.__dict__.get('context', None)
        if context:
            prompt = '%s(%s): ' % (name, context)
        else:
            prompt = '%s: ' % name

        user_input = input(prompt).strip()
        command_name = user_input.split(' ')[0]
        arguments_string = ' '.join(user_input.split(' ')[1:])
        arguments = ArgumentParser()(arguments_string)

        return command_name, arguments

    def lookup_command(self, command_input):
        for command in self.namespace:
            if command.command == command_input:
                return command
        raise IncorrectCommand(command_input)

    @Command('Print this message', number=998)
    def help(self, command_name: 'Specifies command name to get detailed usage information.'=''):
        """
        Prints list of available commands of current mode, or detailed command info if command name is specified.
        """

        if not command_name:
            logger.debug('printing basic help')
            print('Available commands:')
            for command in sorted(self.namespace, key=lambda x: x.number):
                print(command.short_help)
            print()

        else:
            logger.debug('printing detailed help for "%s"' % command_name)
            try:
                command = self.lookup_command(command_name)
            except IncorrectCommand as e:
                print('Incorrect command: %s' % e.msg)
            else:
                print(command.long_help)
            print()

    @Command(number='999')
    def exit(self):
        raise StopIteration


class ArgumentParser:
    def __init__(self):
        self.tokens = ' "\'\n'
        self.curr_token = None
        self.prev_token = None
        self.buffer = ''

        self.arguments = []

        self.quote = None

    def __call__(self, argument_string):
        logger.log(5, 'start parsing arguments (%s)' % argument_string)
        for symbol in argument_string.strip():
            logger.log(5, 'symbol (%s)' % symbol)
            if self.quote:
                if symbol == self.quote:
                    self.process_token(symbol)
                else:
                    self.buffer += symbol
            elif symbol in self.tokens:
                self.process_token(symbol)
            else:
                self.buffer += symbol

        self.process_token('\n')
        logger.log(5, 'end parsing arguments')
        return tuple(self.arguments)

    def change_token(self, new_token):
        if new_token == '\n':
            token = '\\n'
        else:
            token = new_token
        logger.log(5, 'changing token from (%s) to (%s)' % (self.curr_token, token))

        self.prev_token = self.curr_token
        self.curr_token = new_token

    def flush_buffer(self):
        buffer = self.buffer
        logger.log(5, 'got (%s), flushing buffer' % buffer)
        self.buffer = ''
        return buffer

    def process_token(self, symbol):
        self.change_token(symbol)

        if self.curr_token in ' \n':
            if self.prev_token and self.prev_token in '"\'':
                data = self.flush_buffer()
                self.arguments.append(data)
            else:
                data = self.flush_buffer()
                if data:
                    self.arguments.append(data)

        elif self.curr_token in '"\'':
            if self.quote is None:
                self.quote = self.curr_token
            else:
                self.quote = None


class CustomException(Exception):
    def __init__(self, msg=''):
        self.msg = msg


class IncorrectCommand(CustomException):
    pass


class IncorrectArguments(CustomException):
    pass
