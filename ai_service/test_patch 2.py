import importlib.metadata
class DummyEntryPoints:
    def __iter__(self): return iter([])
    def select(self, **kwargs): return []

importlib.metadata.entry_points = lambda **kwargs: DummyEntryPoints()

print("Patched entry_points. Importing main...")
import main
print("Main imported successfully!")
