from rest_framework import viewsets, serializers
from .models import Product, Warehouse, StockLevel


class ProductSerializer(serializers.ModelSerializer):
    total_stock = serializers.ReadOnlyField()
    category_name = serializers.CharField(source='category.name', read_only=True, default='')
    unit_name = serializers.CharField(source='unit.abbreviation', read_only=True, default='')
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = '__all__'

    def get_image_url(self, obj):
        try:
            if obj.image:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.image.url)
                return obj.image.url
        except Exception:
            pass
        return None


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'


class StockLevelSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    available = serializers.ReadOnlyField()

    class Meta:
        model = StockLevel
        fields = '__all__'


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ['product_type', 'category', 'brand', 'is_active']
    search_fields = ['name', 'sku', 'barcode']


class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer


class StockLevelViewSet(viewsets.ModelViewSet):
    queryset = StockLevel.objects.all()
    serializer_class = StockLevelSerializer
    filterset_fields = ['product', 'warehouse']
