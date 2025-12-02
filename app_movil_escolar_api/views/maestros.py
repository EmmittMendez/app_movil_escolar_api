from django.db.models import *
from django.db import transaction
from app_movil_escolar_api.serializers import UserSerializer
from app_movil_escolar_api.serializers import *
from app_movil_escolar_api.models import *
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth.models import Group
import json
from django.shortcuts import get_object_or_404

class MaestrosAll(generics.CreateAPIView):
    #Obtener todos los maestros
    # Necesita permisos de autenticación de usuario para poder acceder a la petición
    permission_classes = (permissions.IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        #Usamos select_related para evitar N+1 consultas al obtener el usuario
        maestros = Maestros.objects.select_related('user').filter(user__is_active=1).order_by("id")
        lista = MaestroSerializer(maestros, many=True).data
        for maestro in lista:
            if isinstance(maestro, dict) and "materias_json" in maestro:
                try:
                    maestro["materias_json"] = json.loads(maestro["materias_json"])
                except Exception:
                    maestro["materias_json"] = []
        return Response(lista, 200)
    
class MaestrosView(generics.CreateAPIView):

    def get(self, request, *args, **kwargs):
        maestros = Maestros.objects.select_related('user').filter(id=request.GET.get("id")).first()
        if not maestros:
            return Response({"error": "Maestro no encontrado"}, 404)
        maestros = MaestroSerializer(maestros, many=False).data
        
        # Parsear materias_json si existe
        if isinstance(maestros, dict) and "materias_json" in maestros:
            try:
                maestros["materias_json"] = json.loads(maestros["materias_json"])
            except Exception:
                maestros["materias_json"] = []
        
        # Si todo es correcto, regresamos la información
        return Response(maestros, 200)

    #Registrar nuevo usuario maestro
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user = UserSerializer(data=request.data)
        if user.is_valid():
            role = request.data['rol']
            first_name = request.data['first_name']
            last_name = request.data['last_name']
            email = request.data['email']
            password = request.data['password']
            existing_user = User.objects.filter(email=email).first()
            if existing_user:
                return Response({"message":"Username "+email+", is already taken"},400)
            user = User.objects.create( username = email,
                                        email = email,
                                        first_name = first_name,
                                        last_name = last_name,
                                        is_active = 1)
            #Cifrar la contraseña y asignar grupo/rol
            user.set_password(password)
            group, created = Group.objects.get_or_create(name=role)
            group.user_set.add(user)
            user.save()
            #Create a profile for the user
            maestro = Maestros.objects.create(user=user,
                                            id_trabajador= request.data["id_trabajador"],
                                            fecha_nacimiento= request.data["fecha_nacimiento"],
                                            telefono= request.data["telefono"],
                                            rfc= request.data["rfc"].upper(),
                                            cubiculo= request.data["cubiculo"],
                                            area_investigacion= request.data["area_investigacion"],
                                            materias_json = json.dumps(request.data["materias_json"]))
            return Response({"Maestro creado con ID= ": maestro.id }, 201)
        return Response(user.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Actualizar datos del maestro
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        permission_classes = (permissions.IsAuthenticated,)
        
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno, no puede editar maestros
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para editar maestros"}, status=403)
        
        # Primero obtenemos el maestro a actualizar
        maestro = get_object_or_404(Maestros, id=request.data["id"])
        
        # Si es maestro, solo puede editarse a sí mismo
        if 'maestro' in user_groups:
            # Verificar si el maestro autenticado es el mismo que se quiere editar
            try:
                maestro_autenticado = Maestros.objects.get(user=user)
                if maestro.id != maestro_autenticado.id:
                    return Response({"error": "Solo puedes editar tu propio perfil"}, status=403)
            except Maestros.DoesNotExist:
                return Response({"error": "No tienes un perfil de maestro asociado"}, status=403)
        
        # Actualizar campos del maestro
        maestro.id_trabajador = request.data.get("id_trabajador", maestro.id_trabajador)
        maestro.fecha_nacimiento = request.data.get("fecha_nacimiento", maestro.fecha_nacimiento)
        maestro.telefono = request.data.get("telefono", maestro.telefono)
        maestro.rfc = request.data.get("rfc", maestro.rfc)
        maestro.cubiculo = request.data.get("cubiculo", maestro.cubiculo)
        maestro.area_investigacion = request.data.get("area_investigacion", maestro.area_investigacion)
        
        # Actualizar materias_json dsi viene en el request
        if "materias_json" in request.data:
            materias = request.data["materias_json"]
            if isinstance(materias, list):
                maestro.materias_json = json.dumps(materias)
            else:
                maestro.materias_json = materias
        
        maestro.save()
        
        # Actualizamos los datos del usuario asociado (tabla auth_user de Django)
        user = maestro.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.email = request.data.get("email", user.email)
        user.save()
        
        return Response({"message": "Maestro actualizado correctamente", "maestro": MaestroSerializer(maestro).data}, 200)

    # Eliminar maestro con delete (Borrar realmente)
    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno o maestro, no puede eliminar maestros
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para eliminar maestros"}, status=403)
        
        if 'maestro' in user_groups:
            return Response({"error": "Los maestros no tienen permiso para eliminar maestros"}, status=403)
        
        # Solo Admin puede eliminar maestros
        maestro = get_object_or_404(Maestros, id=request.GET.get("id"))
        try:
            maestro.user.delete()
            return Response({"details":"Maestro eliminado"},200)
        except Exception as e:
            return Response({"details":"Algo pasó al eliminar"},400)
    
    #Eliminar maestro (Desactivar usuario)
    # @transaction.atomic
    # def delete(self, request, *args, **kwargs):
    #     id_maestro = kwargs.get('id_maestro', None)
    #     if id_maestro:
    #         try:
    #             maestro = Maestros.objects.get(id=id_maestro)
    #             user = maestro.user
    #             user.is_active = 0
    #             user.save()
    #             return Response({"message":"Maestro con ID "+str(id_maestro)+" eliminado correctamente."},200)
    #         except Maestros.DoesNotExist:
    #             return Response({"message":"Maestro con ID "+str(id_maestro)+" no encontrado."},404)
    #     return Response({"message":"Se necesita el ID del maestro."},400)   