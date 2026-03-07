from rest_framework import viewsets, serializers
from .models import Customer, Supplier, Opportunity


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = '__all__'


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class OpportunitySerializer(serializers.ModelSerializer):
    weighted_amount = serializers.ReadOnlyField()

    class Meta:
        model = Opportunity
        fields = '__all__'


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    filterset_fields = ['customer_type', 'doc_type', 'is_active']
    search_fields = ['name', 'doc_number', 'email']


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ['name', 'doc_number']


class OpportunityViewSet(viewsets.ModelViewSet):
    queryset = Opportunity.objects.all()
    serializer_class = OpportunitySerializer
    filterset_fields = ['stage', 'priority', 'assigned_to']
