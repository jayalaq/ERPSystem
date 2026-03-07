from rest_framework import viewsets, serializers
from .models import POSSale, POSSaleItem


class POSSaleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = POSSaleItem
        fields = '__all__'


class POSSaleSerializer(serializers.ModelSerializer):
    items = POSSaleItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default='')
    seller_name = serializers.CharField(source='seller.get_full_name', read_only=True, default='')

    class Meta:
        model = POSSale
        fields = '__all__'


class POSSaleViewSet(viewsets.ModelViewSet):
    queryset = POSSale.objects.all()
    serializer_class = POSSaleSerializer
    filterset_fields = ['status', 'doc_type', 'payment_method']
    search_fields = ['series', 'correlative']
