from typing import List
from .commands import SearchCommand

class SearchCommandInvoker:
    def __init__(self):
        self._commands: List[SearchCommand] = []
        self._history: List[SearchCommand] = []

    def execute_command(self, command: SearchCommand):
        result = command.execute()
        self._history.append(command)
        return result

    def undo_last(self):
        if self._history:
            command = self._history.pop()
            command.undo()