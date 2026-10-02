from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Route, AirfareObservation, CPIAugmentationIndex


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = "__all__"


class AirfareObservationSerializer(serializers.ModelSerializer):
    route_code = serializers.CharField(source="route.__str__", read_only=True)

    class Meta:
        model = AirfareObservation
        fields = "__all__"


class CPIAugmentationIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = CPIAugmentationIndex
        fields = "__all__"


class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer


class AirfareObservationViewSet(viewsets.ModelViewSet):
    queryset = AirfareObservation.objects.all()
    serializer_class = AirfareObservationSerializer


class CPIAugmentationIndexViewSet(viewsets.ModelViewSet):
    queryset = CPIAugmentationIndex.objects.all()
    serializer_class = CPIAugmentationIndexSerializer


@api_view(["GET"])
def api_status_view(request):
    """API Root status and metadata view."""
    return Response(
        {
            "system": "VayuIndex Domestic Indian Airfare & CPI Engine",
            "version": "1.0.0",
            "status": "operational",
            "endpoints": {
                "routes": "/api/routes/",
                "fares": "/api/fares/",
                "cpi-indices": "/api/cpi-indices/",
            },
        }
    )
