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
from django.shortcuts import get_object_or_404

#Esta funcion regresa todos los alumnos registrados 
class AlumnosAll(generics.CreateAPIView):
    #Aquí se valida la autenticación del usuario
    permission_classes = (permissions.IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        #Usamos select_related para evitar N+1 consultas al obtener el usuario
        alumnos = Alumnos.objects.select_related('user').filter(user__is_active = 1).order_by("id")
        lista = AlumnoSerializer(alumnos, many=True).data
        
        return Response(lista, 200)
    
class AlumnosView(generics.CreateAPIView):
    # Verifica que el usuario esté autenticado solo para métodos que no sean POST
    # def get_permissions(self):
    #     """
    #     Solo requiere autenticación para GET, PUT, DELETE
    #     POST (registro) puede ser público
    #     """
    #     if self.request.method == 'POST':
    #         return [permissions.AllowAny()]
    #     return [permissions.IsAuthenticated()]
    
    def get(self, request, *args, **kwargs):
        alumno = Alumnos.objects.select_related('user').filter(id=request.GET.get("id")).first()
        if not alumno:
            return Response({"error": "Alumno no encontrado"}, 404)
        alumno = AlumnoSerializer(alumno, many=False).data
        # Si todo es correcto, regresamos la información
        return Response(alumno, 200)
    
    #Registrar nuevo usuario
    @transaction.atomic
    def post(self, request, *args, **kwargs):

        user = UserSerializer(data=request.data)
        if user.is_valid():
            #Grab user data
            role = request.data['rol']
            first_name = request.data['first_name']
            last_name = request.data['last_name']
            email = request.data['email']
            password = request.data['password']
            #Valida si existe el usuario o bien el email registrado
            existing_user = User.objects.filter(email=email).first()

            if existing_user:
                return Response({"message":"Username "+email+", is already taken"},400)

            user = User.objects.create( username = email,
                                        email = email,
                                        first_name = first_name,
                                        last_name = last_name,
                                        is_active = 1)

            #Cifrar la contraseña
            user.set_password(password)
            
            #Asignar grupo/rol
            group, created = Group.objects.get_or_create(name=role)
            group.user_set.add(user)
            user.save()

            #Create a profile for the user
            alumno = Alumnos.objects.create(user=user,
                                            matricula= request.data["matricula"],
                                            curp= request.data["curp"].upper(),
                                            rfc= request.data["rfc"].upper(),
                                            fecha_nacimiento= request.data["fecha_nacimiento"],
                                            edad= request.data["edad"],
                                            telefono= request.data["telefono"],
                                            ocupacion= request.data["ocupacion"])

            return Response({"Alumno creado con ID= ": alumno.id }, 201)

        return Response(user.errors, status=status.HTTP_400_BAD_REQUEST)

    # Actualizar datos del alumno
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        permission_classes = (permissions.IsAuthenticated,)
        
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno, no puede editar alumnos
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para editar"}, status=403)
        
        # Primero obtenemos el alumno a actualizar
        alumno = get_object_or_404(Alumnos, id=request.data["id"])
        
        # Actualizar campos del alumno
        alumno.matricula = request.data["matricula"]
        alumno.curp = request.data["curp"].upper()
        alumno.rfc = request.data["rfc"].upper()
        alumno.fecha_nacimiento = request.data["fecha_nacimiento"]
        alumno.edad = request.data["edad"]
        alumno.telefono = request.data["telefono"]
        alumno.ocupacion = request.data["ocupacion"]
        alumno.save()
        
        # Actualizamos los datos del usuario asociado (tabla auth_user de Django)
        user = alumno.user
        user.first_name = request.data["first_name"]
        user.last_name = request.data["last_name"]
        user.email = request.data["email"]
        user.save()
        
        return Response({"message": "Alumno actualizado correctamente", "alumno": AlumnoSerializer(alumno).data}, 200)

    # Eliminar alumno con delete (Borrar realmente)
    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        # Verificar el rol del usuario autenticado
        user = request.user
        user_groups = user.groups.values_list('name', flat=True)
        
        # Si es alumno, no puede eliminar alumnos
        if 'alumno' in user_groups:
            return Response({"error": "Los alumnos no tienen permiso para eliminar"}, status=403)
        
        alumno = get_object_or_404(Alumnos, id=request.GET.get("id"))
        try:
            alumno.user.delete()
            return Response({"details":"Alumno eliminado"},200)
        except Exception as e:
            return Response({"details":"Algo pasó al eliminar"},400)
