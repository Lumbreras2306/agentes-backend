from rest_framework.renderers import JSONRenderer, BaseRenderer
import json


class PNGRenderer(BaseRenderer):
    """Renderer para imágenes PNG"""
    media_type = 'image/png'
    format = 'png'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Si data es bytes, devolverlo directamente
        if isinstance(data, bytes):
            return data
        # Si es otro tipo, intentar convertirlo a bytes
        if hasattr(data, 'content'):
            return data.content
        return bytes(data) if data else b''


class GIFRenderer(BaseRenderer):
    """Renderer para imágenes GIF animadas"""
    media_type = 'image/gif'
    format = 'gif'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Si data es bytes, devolverlo directamente
        if isinstance(data, bytes):
            return data
        # Si es otro tipo, intentar convertirlo a bytes
        if hasattr(data, 'content'):
            return data.content
        return bytes(data) if data else b''


class CompactJSONRenderer(JSONRenderer):
    """Renderer que formatea JSON con listas compactas"""
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''
        
        # Convertir a JSON con formato personalizado
        json_str = self._format_json(data)
        return json_str.encode('utf-8')
    
    def _format_json(self, obj, indent=0):
        """Formatea JSON con listas en una sola línea"""
        indent_str = "  " * indent
        
        if isinstance(obj, dict):
            if not obj:
                return "{}"
            
            items = []
            for key, value in obj.items():
                formatted_value = self._format_json(value, indent + 1)
                items.append(f'{indent_str}  "{key}": {formatted_value}')
            
            return "{\n" + ",\n".join(items) + "\n" + indent_str + "}"
        
        elif isinstance(obj, list):
            if not obj:
                return "[]"
            
            # Si la lista contiene solo números o strings simples, mantenerla en una línea
            if all(isinstance(item, (int, float, str, bool, type(None))) for item in obj):
                return json.dumps(obj, ensure_ascii=False)
            
            # Si contiene listas (como grid), formatear cada sublista en su línea
            if all(isinstance(item, list) for item in obj):
                items = [json.dumps(item, ensure_ascii=False) for item in obj]
                return "[\n" + indent_str + "  " + (",\n" + indent_str + "  ").join(items) + f"\n{indent_str}]"
            
            # Para otros casos, formato normal
            items = []
            for item in obj:
                formatted_item = self._format_json(item, indent + 1)
                items.append(f"{indent_str}  {formatted_item}")
            
            return "[\n" + ",\n".join(items) + f"\n{indent_str}]"
        
        else:
            return json.dumps(obj, ensure_ascii=False)
