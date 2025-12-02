from django.db.models import *
from django.db import transaction
# from app_movil_escolar_api.serializers import UserSerializer
from app_movil_escolar_api.serializers import *
from app_movil_escolar_api.models import *
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
# from django.contrib.auth.models import Group
import json
from django.shortcuts import get_object_or_404

class MateriasAll(generics.CreateAPIView):
    #Obtener todas las materias
    # Necesita permisos de autenticación de usuario para poder acceder a la petición
    permission_classes = (permissions.IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        # Verificar que no sea alumno
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        # Si es alumno, no puede ver materias
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para ver materias"}, status=403)
        
        #Usamos select_related para evitar N+1 consultas (profesor y su usuario)
        materias = Materias.objects.select_related('profesor', 'profesor__user').all().order_by("id")
        serializer = MateriaSerializer(materias, many=True)
        return Response(serializer.data, 200)

class MateriasView(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno, no puede ver materias
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para ver materias"}, status=403)
        
        materia = Materias.objects.select_related('profesor', 'profesor__user').filter(id=request.GET.get("id")).first()
        if not materia:
            return Response({"error": "Materia no encontrada"}, 404)
        serializer = MateriaSerializer(materia, many=False)
        return Response(serializer.data, 200)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno, no puede crear materias
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para crear materias"}, status=403)
        
        # Si es maestro, no puede crear materias
        if 'maestro' in user_groups:
            return Response({"error": "Los maestros no tienen permiso para crear materias"}, status=403)
        
        data = request.data
        
        # Verificar que el NRC no exista
        if Materias.objects.filter(nrc=data.get("nrc")).exists():
            return Response({"error": "El NRC ya existe"}, 400)
        
        # Obtener el profesor si viene
        profesor = None
        if data.get("profesor_id"):
            profesor = get_object_or_404(Maestros, id=data.get("profesor_id"))
        
        materia = Materias.objects.create(
            nrc=data.get("nrc"),
            nombre=data.get("nombre"),
            seccion=data.get("seccion"),
            dias_json=json.dumps(data.get("dias_json", [])),
            hora_inicio=data.get("hora_inicio"),
            hora_fin=data.get("hora_fin"),
            salon=data.get("salon"),
            programa_educativo=data.get("programa_educativo"),
            profesor=profesor,
            creditos=data.get("creditos")
        )
        materia.save()
        return Response({"message": "Materia creada", "id": materia.id}, 201)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        # Solo admin puede editar
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        if 'alumno' in user_groups or 'maestro' in user_groups:
            return Response({"error": "No tienes permiso para editar materias"}, status=403)
        
        materia = get_object_or_404(Materias, id=request.data.get("id"))
        data = request.data
        
        materia.nrc = data.get("nrc", materia.nrc)
        materia.nombre = data.get("nombre", materia.nombre)
        materia.seccion = data.get("seccion", materia.seccion)
        materia.hora_inicio = data.get("hora_inicio", materia.hora_inicio)
        materia.hora_fin = data.get("hora_fin", materia.hora_fin)
        materia.salon = data.get("salon", materia.salon)
        materia.programa_educativo = data.get("programa_educativo", materia.programa_educativo)
        materia.creditos = data.get("creditos", materia.creditos)
        
        if "dias_json" in data:
            dias = data["dias_json"]
            if isinstance(dias, list):
                materia.dias_json = json.dumps(dias)
            else:
                materia.dias_json = dias
        
        if data.get("profesor_id"):
            profesor = get_object_or_404(Maestros, id=data.get("profesor_id"))
            materia.profesor = profesor
        
        materia.save()
        return Response({"message": "Materia actualizada", "materia": MateriaSerializer(materia).data}, 200)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # Solo admin puede eliminar
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        if 'alumno' in user_groups or 'maestro' in user_groups:
            return Response({"error": "No tienes permiso para eliminar materias"}, status=403)
        
        materia = get_object_or_404(Materias, id=request.GET.get("id"))
        materia.delete()
        return Response({"message": "Materia eliminada"}, 200)

class MaestrosParaMaterias(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        maestros = Maestros.objects.filter(user__is_active=1).order_by("id")
        serializer = MaestroSerializer(maestros, many=True)
        return Response(serializer.data, 200)