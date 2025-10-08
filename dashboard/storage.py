def get_storage():
    
    class _Null:
        def list_csv(self, limit=10):
            return []
    
    return _Null()