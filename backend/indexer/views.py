from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Airport, FlightRoute, FareObservation, DailyCPIIndex


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = "__all__"


class FlightRouteSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source="__str__", read_only=True)
    origin_details = AirportSerializer(source="origin", read_only=True)
    destination_details = AirportSerializer(source="destination", read_only=True)

    class Meta:
        model = FlightRoute
        fields = "__all__"


class FareObservationSerializer(serializers.ModelSerializer):
    route_code = serializers.CharField(source="route.__str__", read_only=True)

    class Meta:
        model = FareObservation
        fields = "__all__"


class DailyCPIIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyCPIIndex
        fields = "__all__"


class AirportViewSet(viewsets.ModelViewSet):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer


class FlightRouteViewSet(viewsets.ModelViewSet):
    queryset = FlightRoute.objects.select_related("origin", "destination").all()
    serializer_class = FlightRouteSerializer


class FareObservationViewSet(viewsets.ModelViewSet):
    queryset = FareObservation.objects.select_related("route__origin", "route__destination").all()
    serializer_class = FareObservationSerializer


class DailyCPIIndexViewSet(viewsets.ModelViewSet):
    queryset = DailyCPIIndex.objects.all()
    serializer_class = DailyCPIIndexSerializer


@api_view(["GET"])
def api_status_view(request):
    """API Root discovery and status endpoint."""
    return Response(
        {
            "service": "VayuIndex API",
            "description": "Domestic Indian Airfare Volatility & CPI Augmentation Engine",
            "version": "1.0.0",
            "status": "operational",
            "endpoints": {
                "airports": "/api/airports/",
                "routes": "/api/routes/",
                "fares": "/api/fares/",
                "cpi-indices": "/api/cpi-indices/",
            },
        }
    )
