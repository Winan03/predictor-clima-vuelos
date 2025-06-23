        // ============= CONFIGURACIÓN DE FIREBASE =============
        const firebaseConfig = {
            // REEMPLAZA ESTOS VALORES CON TU CONFIGURACIÓN DE FIREBASE
            apiKey: "AIzaSyDtgbgt93iRiucXkGa6mjD6U9bxHTrpKMI",
            authDomain: "sistema-predictivo-aereo.firebaseapp.com",
            databaseURL: "https://sistema-predictivo-aereo-default-rtdb.firebaseio.com",
            projectId: "sistema-predictivo-aereo",
            storageBucket: "sistema-predictivo-aereo.firebasestorage.app",
            messagingSenderId: "828520564895",
            appId: "1:828520564895:web:9a134b38c5cf377c997aaa",
            measurementId: "G-1YX5EXQKD7"
        };

        // Inicializar Firebase
        firebase.initializeApp(firebaseConfig);
        const auth = firebase.auth();

        // Variables globales
        let currentUser = null;
        const vuelosPredichos = new Set();
        let contadorVuelos = 0;
        let ahorroAcumulado = 0;
        let prediccionesRealizadas = 0;

        // ============= AUTENTICACIÓN =============
        auth.onAuthStateChanged((user) => {
            if (user) {
                currentUser = user;
                showMainApp();

                const name = user.displayName || 'Usuario';
                const photo = user.photoURL || '/static/default-profile.png';

                document.getElementById('user-name').textContent = name;
                document.getElementById('profile-pic').src = photo;

                loadStats();
            } else {
                currentUser = null;
                showAuthSection();
            }
        });

        function toggleAuthView() {
            
            showMainApp();
        }

        
        function toggleUserMenu() {
            const menu = document.getElementById('user-menu');
            menu.classList.toggle('hidden');
        }

        function showAuthSection() {
            document.getElementById('auth-section').classList.remove('hidden');
            document.getElementById('main-app').classList.add('hidden');
        }

        function showMainApp() {
            document.getElementById('auth-section').classList.add('hidden');
            document.getElementById('main-app').classList.remove('hidden');
        }

        function showLoginForm() {
            document.getElementById('login-form').classList.remove('hidden');
            document.getElementById('register-form').classList.add('hidden');

            document.getElementById('auth-title').textContent = '🔐 Iniciar Sesión';
            document.getElementById('auth-subtitle').textContent = 'Inicie sesión para acceder al predictor de vuelos';
        }

        function showRegisterForm() {
            document.getElementById('login-form').classList.add('hidden');
            document.getElementById('register-form').classList.remove('hidden');

            document.getElementById('auth-title').textContent = '📝 Registro de Usuario';
            document.getElementById('auth-subtitle').textContent = 'Cree una cuenta para usar el predictor de vuelos';
        }

        async function loginUser() {
            const email = document.getElementById('login-email').value.trim();
            const password = document.getElementById('login-password').value.trim();

            if (!email || !password) {
                showError('Por favor, complete todos los campos');
                return;
            }

            // Validación de formato de correo
            if (!/^[a-zA-Z][a-zA-Z0-9_.+-]*@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$/.test(email)) {
                showError('Ingrese un correo electrónico válido (ej: ejemplo@dominio.com).');
                return;
            }

            // Validación de contraseña mínima
            if (password.length < 6) {
                showError('La contraseña debe tener al menos 6 caracteres.');
                return;
            }

            if (!/[A-Za-z]/.test(password)) {
                showError('La contraseña debe contener al menos una letra.');
                return;
            }

            if (!/\d/.test(password)) {
                showError('La contraseña debe contener al menos un número.');
                return;
            }

            showAuthLoading(true);

            try {
                const userCredential = await auth.signInWithEmailAndPassword(email, password);
                const user = userCredential.user;

                const userName = user.displayName || email.split('@')[0];
                document.getElementById('user-name').textContent = userName;
                localStorage.setItem('userName', userName);

                showSuccess('Inicio de sesión exitoso');
                toggleAuthView();
            } catch (error) {
                console.error('🔐 Error completo de login:', error);

                if (error.code) {
                    showError(getAuthErrorMessage(error.code));
                } else if (error.message?.toLowerCase().includes("network")) {
                    showError("Problema de red al iniciar sesión. Verifica tu conexión.");
                } else if (error.message?.toLowerCase().includes("popup")) {
                    showError("Error con el popup de autenticación. Intenta nuevamente.");
                } else {
                    showError("Error inesperado durante el login: " + (error.message || "sin mensaje."));
                }
            } finally {
                showAuthLoading(false);
            }

        }


        window.onload = () => {
            const savedName = localStorage.getItem('userName');
            if (savedName) {
                document.getElementById('user-name').textContent = savedName;
            }

            document.getElementById('register-photo').addEventListener('change', function (event) {
                const file = event.target.files[0];
                const preview = document.getElementById('preview-photo');
                if (file) {
                    preview.src = URL.createObjectURL(file);
                } else {
                    preview.src = "/static/default-profile.png";
                }
            });
        };


        async function registerUser() {
            const email = document.getElementById('register-email').value.trim();
            const password = document.getElementById('register-password').value.trim();
            const confirmPassword = document.getElementById('register-confirm').value.trim();
            const nombre = document.getElementById('register-name').value.trim();
            const username = document.getElementById('register-username').value.trim().toLowerCase();
            const photoFile = document.getElementById('register-photo').files[0];

            // Validación del nombre
            const palabras = nombre.split(' ').filter(p => p.length > 0);
            if (palabras.length < 4) {
                showError('Por favor ingrese su nombre completo (ej: Ana María López Castillo).');
                return;
            }
            if (palabras.length > 6) {
                showError('Nombre muy largo: ingrese solo sus 2 nombres y 2 apellidos.');
                return;
            }
            if (!/^[a-zA-ZÁÉÍÓÚÑáéíóúñ\s]+$/.test(nombre)) {
                showError('El nombre solo debe contener letras y espacios (sin números ni símbolos).');
                return;
            }

            // Validar campos básicos
            if (!email || !password || !confirmPassword || !nombre || !username) {
                showError('Por favor, complete todos los campos');
                return;
            }

            // Validar correo
            if (!/^[a-zA-Z][a-zA-Z0-9_.+-]*@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$/.test(email)) {
                showError('Ingrese un correo electrónico válido (ej: ejemplo@dominio.com).');
                return;
            }

            // Validar username
            if (!/^[a-zA-Z0-9_.-]{4,20}$/.test(username)) {
                showError('El nombre de usuario debe tener entre 4 y 20 caracteres y solo letras, números o guiones.');
                return;
            }

            // Validar contraseña
            if (password.length < 6) {
                showError('La contraseña debe tener al menos 6 caracteres.');
                return;
            }
            if (!/[A-Za-z]/.test(password)) {
                showError('La contraseña debe contener al menos una letra.');
                return;
            }
            if (!/\d/.test(password)) {
                showError('La contraseña debe contener al menos un número.');
                return;
            }
            if (password !== confirmPassword) {
                showError('Las contraseñas no coinciden');
                return;
            }

            showAuthLoading(true);

            try {
                const userCredential = await auth.createUserWithEmailAndPassword(email, password);
                const user = userCredential.user;
                let photoURL = "/static/default-profile.png";

                // ✅ SUBIDA DE IMAGEN CON MANEJO DE ERRORES DETALLADO
                if (photoFile) {
                    try {
                        const storageRef = firebase.storage().ref();
                        const userPhotoRef = storageRef.child(`users/${user.uid}/profile.jpg`);
                        await userPhotoRef.put(photoFile);
                        photoURL = await userPhotoRef.getDownloadURL();
                    } catch (uploadError) {
                        console.error("Error al subir imagen:", uploadError);
                        showError("La cuenta se creó, pero no se pudo subir la imagen. Puedes intentarlo desde tu perfil más adelante.");
                    }
                }

                await user.updateProfile({
                    displayName: nombre,
                    photoURL: photoURL
                });

                localStorage.setItem('userName', nombre);
                localStorage.setItem('userPhoto', photoURL);
                document.getElementById('user-name').textContent = nombre;
                document.getElementById('profile-pic').src = photoURL;

                showSuccess('Registro exitoso. Bienvenido!');
                toggleAuthView();

            } catch (error) {
                console.error('⚠️ Error completo:', error);
                const codigo = error?.code || 'error-desconocido';
                showError(getAuthErrorMessage(codigo));
            } finally {
                showAuthLoading(false);
            }
        }

        function generarPasswordFuerte(longitud = 12) {
            const caracteres = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>?";
            let password = "";
            for (let i = 0; i < longitud; i++) {
                password += caracteres.charAt(Math.floor(Math.random() * caracteres.length));
            }

            const input = document.getElementById('register-password');
            const confirm = document.getElementById('register-confirm');
            input.value = password;
            confirm.value = password;
        }


        function togglePassword(inputId, iconElement) {
            const input = document.getElementById(inputId);
            if (input.type === 'password') {
                input.type = 'text';
                iconElement.textContent = '🙈';
            } else {
                input.type = 'password';
                iconElement.textContent = '👁️';
            }
        }

        function mostrarBurbujaPrediccion(mensaje = "✅ Predicción hecha") {
            const bubble = document.createElement('div');
            bubble.className = 'bubble-alert';
            bubble.textContent = mensaje;

            const icon = document.querySelector('.user-icon') || document.body;
            icon.appendChild(bubble);

            bubble.style.top = '-10px';
            bubble.style.left = '50%';
            bubble.style.transform = 'translateX(-50%)';

            setTimeout(() => {
                bubble.remove();
            }, 2000);
            }


        async function logoutUser() {
            try {
                await auth.signOut();
                showSuccess('Sesión cerrada correctamente');
            } catch (error) {
                console.error('Error al cerrar sesión:', error);
                showError('Error al cerrar sesión');
            }
        }

        function showAuthLoading(show) {
            const forms = document.getElementById('auth-forms');
            const loading = document.getElementById('auth-loading');
            
            if (show) {
                forms.classList.add('hidden');
                loading.classList.remove('hidden');
            } else {
                forms.classList.remove('hidden');
                loading.classList.add('hidden');
            }
        }

        function getAuthErrorMessage(errorCode) {
    if (!errorCode || typeof errorCode !== 'string') {
        return 'Error desconocido. Intente nuevamente o revise la consola para más detalles.';
    }

        switch (errorCode) {
            case 'auth/user-not-found':
                return 'El usuario no está registrado.';
            case 'auth/wrong-password':
                return 'La contraseña es incorrecta.';
            case 'auth/invalid-login-credentials':
                return 'Correo o contraseña incorrectos.';
            case 'auth/email-already-in-use':
                return 'El correo ya está registrado.';
            case 'auth/weak-password':
                return 'La contraseña es muy débil.';
            case 'auth/invalid-email':
                return 'Correo electrónico inválido.';
            default:
                return `Error de autenticación no manejado. Código recibido: ${errorCode}`;
        }
    }

        function generarDatosVuelo() {
            const ciudades = ['lima', 'arequipa', 'trujillo', 'piura', 'cajamarca', 'puno'];
            const pasajeros = [80, 95, 110, 120, 135, 150, 165, 180];
            const costosBase = [85, 95, 100, 110, 120, 135, 150];
            
            const horasUsadas = new Set();
            const vuelosGroups = document.querySelectorAll('.vuelo-group');
            vuelosGroups.forEach(group => {
                const horaInput = group.querySelector('input[name="hora"]');
                if (horaInput && horaInput.value) {
                    horasUsadas.add(horaInput.value);
                }
            });

            let horaFormateada;
            let intentos = 0;
            do {
                const hora = Math.floor(Math.random() * 17) + 6;
                const minuto = Math.random() < 0.5 ? 0 : 30;
                horaFormateada = `${hora.toString().padStart(2, '0')}:${minuto.toString().padStart(2, '0')}`;
                intentos++;
            } while (horasUsadas.has(horaFormateada) && intentos < 50);

            if (horasUsadas.has(horaFormateada)) {
                const hora = Math.floor(Math.random() * 17) + 6;
                const minuto = Math.floor(Math.random() * 60);
                horaFormateada = `${hora.toString().padStart(2, '0')}:${minuto.toString().padStart(2, '0')}`;
            }
            
            return {
                ciudad: ciudades[Math.floor(Math.random() * ciudades.length)],
                pasajeros: pasajeros[Math.floor(Math.random() * pasajeros.length)],
                costo: costosBase[Math.floor(Math.random() * costosBase.length)],
                hora: horaFormateada
            };
        }


        function crearIdVuelo(ciudad, fecha, hora) {
            return `${ciudad}-${fecha}-${hora}`;
        }

        function yaFuePredicho(ciudad, fecha, hora) {
            const id = crearIdVuelo(ciudad, fecha, hora);
            return vuelosPredichos.has(id);
        }

        function marcarComoPredicho(ciudad, fecha, hora, divVuelo) {
            // Añadir clase de estilo general al vuelo
            divVuelo.classList.add("vuelo-predicho");

            // Verifica si ya tiene botón, y si es así, no lo vuelve a agregar
            if (divVuelo.querySelector(".toggle-btn")) return;

            // Crear botón
            const btnToggle = document.createElement("button");
            btnToggle.textContent = "🔼 Ocultar detalles"; // texto inicial
            btnToggle.className = "toggle-btn bonito";     // clase para estilos
            btnToggle.type = "button";                     // importante para no disparar submit
            btnToggle.style.marginTop = "10px";

            // Agregar funcionalidad
            btnToggle.onclick = () => {
                const detalles = divVuelo.querySelectorAll(".form-group");
                const ocultando = detalles[0].classList.contains("hidden");

                detalles.forEach(el => el.classList.toggle("hidden"));
                btnToggle.textContent = ocultando ? "🔼 Ocultar detalles" : "🔽 Mostrar detalles";
            };

            divVuelo.appendChild(btnToggle);
        }

        function obtenerNumeroVuelo(origen, destino) {
            const vuelo = vuelosProgramados.find(v => v.origen === origen && v.destino === destino);
            return vuelo ? vuelo.numero_vuelo : null;
        }

        // ============= MANEJO DEL FORMULARIO DE PREDICCIÓN =============
        document.getElementById('prediction-form').addEventListener('submit', async function(e) {
            e.preventDefault();

            if (!currentUser || !currentUser.uid) {
                showError('Debe iniciar sesión para realizar predicciones');
                return;
            }

            const vuelosGroups = document.querySelectorAll('.vuelo-group');
            let formData = null;
            let vueloTarget = null;
            let indexVuelo = -1;

            for (let i = 0; i < vuelosGroups.length; i++) {
                const group = vuelosGroups[i];
                if (!group.classList.contains('predicted')) {
                    const inputs = group.querySelectorAll('input, select');
                    const data = {
                        origen: inputs[0].value,
                        ciudad: inputs[1].value,
                        fecha: inputs[2].value,
                        hora: inputs[3].value,
                        pasajeros: parseInt(inputs[4].value),
                        costo: parseFloat(inputs[5].value),
                        user_id: currentUser.uid,
                        numero_vuelo: obtenerNumeroVuelo(inputs[0].value, inputs[1].value)
                    };

                    if (!data.origen || !data.ciudad || !data.fecha || !data.hora) {
                        showError(`Complete todos los campos del Vuelo ${i + 1}`);
                        return;
                    }

                    if (data.origen === data.ciudad) {
                        showError(`❌ En el Vuelo ${i + 1}, la ciudad de origen y destino no pueden ser iguales.`);
                        return;
                    }

                    vueloTarget = group;
                    formData = data;
                    indexVuelo = i + 1;
                    break;
                }
            }


            if (!formData) {
                showWarning('Todos los vuelos ya fueron procesados');
                return;
            }

            const idVuelo = crearIdVuelo(formData.ciudad, formData.fecha, formData.hora);
            const esRepetido = yaFuePredicho(formData.ciudad, formData.fecha, formData.hora);

            showLoading(true);

            try {
                const response = await fetch('/predecir', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(formData)
                });

                if (!response.ok) {
                    let mensajeError = `Error HTTP: ${response.status}`;
                    try {
                        const data = await response.json();
                        mensajeError = data.error || mensajeError;
                    } catch (e) {}
                    throw new Error(mensajeError);
                }

                const result = await response.json();

                showResults(result);
                // ⭐️ Inicializar explicaciones visuales/textuales
                //inicializarExplicacion(result);

                mostrarBurbujaPrediccion(`✈️ ${formData.ciudad.toUpperCase()} predicho`);
                inicializarExplicacion(result);
                
                if (!esRepetido) {
                    vuelosPredichos.add(idVuelo); // solo si no era repetido
                    marcarComoPredicho(formData.ciudad, formData.fecha, formData.hora, vueloTarget);
                    vueloTarget.classList.add('predicted');
                }

                let mensaje = `Vuelo ${indexVuelo} (${formData.ciudad.toUpperCase()} - ${formData.fecha} ${formData.hora}) procesado.`;
                if (esRepetido) mensaje += ' ⚠️ Ya había sido predicho antes (pero se volvió a guardar).';
                if (result.ahorro_estimado) mensaje += ` Ahorro estimado: $${result.ahorro_estimado}`;
                if (result.firebase_guardado) mensaje += ' ✅ Guardado en Firebase';

                showSuccess(mensaje);
                loadStats();

            } catch (error) {
                console.error('Error en predicción:', error);
                showError(error.message);
            } finally {
                showLoading(false);
            }
        });


        function showLoading(show) {
            const button = document.getElementById('predict-btn');
            const spinner = document.getElementById('loading-spinner');
            const text = document.getElementById('predict-btn-text');

            if (show) {
                button.disabled = true;
                spinner.style.display = 'inline-block';
                text.textContent = 'Analizando...';
            } else {
                button.disabled = false;
                spinner.style.display = 'none';
                text.textContent = 'Predecir Retraso';
            }
        }

        function showResults(result) {
            const resultsSection = document.getElementById('results-section');
            const riskIndicator = document.getElementById('risk-indicator');
            const riskText = document.getElementById('risk-text');
            const probabilityFill = document.getElementById('probability-fill');
            const probabilityText = document.getElementById('probability-text');

            document.getElementById('placeholder-prediccion').style.display = 'none';
            document.getElementById('resultado-prediccion').style.display = 'block';


            resultsSection.classList.add('show');

            riskIndicator.className = 'risk-indicator risk-' + result.riesgo.toLowerCase();
            riskText.textContent = `Riesgo ${result.riesgo.toUpperCase()} de Retraso`;

            const probability = Math.round(result.probabilidad_retraso);
            probabilityFill.style.width = probability + '%';
            probabilityText.textContent = probability + '%';

            const oldFecha = document.getElementById('clima-fecha');
            if (oldFecha) oldFecha.remove();

            const fechaPronostico = result.datos_clima.fecha_observacion_peru || result.fecha_hora || 'Fecha no disponible';
            const fechaDiv = document.createElement('div');
            fechaDiv.id = 'clima-fecha';
            fechaDiv.style.textAlign = 'center';
            fechaDiv.style.fontSize = '0.9rem';
            fechaDiv.style.color = '#666';
            fechaDiv.style.marginTop = '5px';
            fechaDiv.innerHTML = `🕓 Clima para: <strong>${fechaPronostico}</strong>`;
            probabilityText.insertAdjacentElement('afterend', fechaDiv);

            updateWeatherInfo(result.datos_clima);
            updateRecommendations(result.recomendaciones || []);
        }

        function agregarVuelo() {
            contadorVuelos++;
            const container = document.getElementById('vuelos-container');
            const index = container.querySelectorAll('.vuelo-group').length;
            const datosAleatorios = generarDatosVuelo();

            const vueloHTML = `
            <div class="vuelo-group" data-index="${index}">
                <button type="button" class="remove-flight-btn" onclick="eliminarVuelo(this)" title="Eliminar vuelo">×</button>
                <h3>Vuelo ${index + 1}</h3>
                <div class="form-group">
                    <label>Ciudad de Destino:</label>
                    <select name="ciudad" required>
                        <option value="">Seleccionar ciudad...</option>
                        <option value="lima" ${datosAleatorios.ciudad === 'lima' ? 'selected' : ''}>Lima</option>
                        <option value="arequipa" ${datosAleatorios.ciudad === 'arequipa' ? 'selected' : ''}>Arequipa</option>
                        <option value="trujillo" ${datosAleatorios.ciudad === 'trujillo' ? 'selected' : ''}>Trujillo</option>
                        <option value="piura" ${datosAleatorios.ciudad === 'piura' ? 'selected' : ''}>Piura</option>
                        <option value="cajamarca" ${datosAleatorios.ciudad === 'cajamarca' ? 'selected' : ''}>Cajamarca</option>
                        <option value="puno" ${datosAleatorios.ciudad === 'puno' ? 'selected' : ''}>Puno</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Fecha del Vuelo:</label>
                    <input type="date" name="fecha" required min="${new Date().toISOString().split('T')[0]}">
                </div>
                <div class="form-group">
                    <label>Hora del Vuelo:</label>
                    <input type="time" name="hora" value="${datosAleatorios.hora}" required>
                </div>
                <div class="form-group">
                    <label>Número estimado de pasajeros:</label>
                    <input type="number" name="pasajeros" min="1" value="${datosAleatorios.pasajeros}" required>
                </div>
                <div class="form-group">
                    <label>Costo estimado por pasajero (USD):</label>
                    <input type="number" name="costo" min="1" value="${datosAleatorios.costo}" required>
                </div>
                <hr>
            </div>`;

            container.insertAdjacentHTML('beforeend', vueloHTML);
            showSuccess(`Nuevo vuelo agregado con hora única (${datosAleatorios.hora}). Ajuste los detalles según sea necesario.`);
            configurarSelectsVuelos();
        }

        function eliminarVuelo(btn) {
            const vueloGroup = btn.closest('.vuelo-group');
            const vueloNumber = vueloGroup.querySelector('h3').textContent;
            
            const inputs = vueloGroup.querySelectorAll('input, select');
            if (inputs.length >= 3) {
                const ciudad = inputs[0].value;
                const fecha = inputs[1].value;
                const hora = inputs[2].value;
                
                if (ciudad && fecha && hora) {
                    const id = crearIdVuelo(ciudad, fecha, hora);
                    vuelosPredichos.delete(id);
                }
            }
            
            vueloGroup.remove();
            
            const remainingFlights = document.querySelectorAll('.vuelo-group');
            remainingFlights.forEach((flight, index) => {
                const h3 = flight.querySelector('h3');
                h3.textContent = `Vuelo ${index + 1}`;
                flight.setAttribute('data-index', index);
            });
            
            showSuccess(`${vueloNumber} eliminado correctamente.`);
        }

        function updateWeatherInfo(datosClima) {
            const weatherInfo = document.getElementById('weather-info');
            
            const weatherCards = [
                { label: 'Temperatura', value: `${datosClima.temperatura || 'N/A'}°C` },
                { label: 'Precipitación', value: `${datosClima.precipitacion || 0} mm` },
                { label: 'Viento', value: `${datosClima.viento_velocidad || 'N/A'} km/h` },
                { label: 'Presión', value: `${datosClima.presion || 'N/A'} hPa` },
                { label: 'Visibilidad', value: `${datosClima.visibilidad || 'N/A'} km` },
                { label: 'Nubosidad', value: `${datosClima.nubosidad || 'N/A'}%` }
            ];

            weatherInfo.innerHTML = weatherCards.map(card => `
                <div class="weather-card">
                    <div class="value">${card.value}</div>
                    <div class="label">${card.label}</div>
                </div>
            `).join('');
        }

        function updateRecommendations(recomendaciones) {
            const recommendationsList = document.getElementById('recommendations-list');
            
            if (recomendaciones && recomendaciones.length > 0) {
                recommendationsList.innerHTML = recomendaciones.map(rec => `<li>${rec}</li>`).join('');
            } else {
                recommendationsList.innerHTML = '<li>No hay recomendaciones específicas disponibles</li>';
            }
        }

        async function loadStats() {
            if (!currentUser) return;
            
            try {
                const response = await fetch('/estadisticas');
                if (response.ok) {
                    const stats = await response.json();
                    
                    document.getElementById('predicciones-hoy').textContent = stats.predicciones_realizadas || 0;
                    document.getElementById('precision-modelo').textContent = stats.modelo_precision || '0%';
                    document.getElementById('retrasos-evitados').textContent = stats.retrasos_evitados || 0;
                    document.getElementById('ahorro-estimado').textContent = `$${(stats.ahorro_estimado_usd || 0).toLocaleString()}`;
                } else {
                    document.getElementById('predicciones-hoy').textContent = '0';
                    document.getElementById('precision-modelo').textContent = '0%';
                    document.getElementById('retrasos-evitados').textContent = '0';
                    document.getElementById('ahorro-estimado').textContent = '$0';
                }
            } catch (error) {
                console.error('Error cargando estadísticas:', error);
                document.getElementById('predicciones-hoy').textContent = '0';
                document.getElementById('precision-modelo').textContent = '0%';
                document.getElementById('retrasos-evitados').textContent = '0';
                document.getElementById('ahorro-estimado').textContent = '$0';
            }
        }
        // ============ INICIALIZACIÓN DE EXPLICACIONES =============
        function inicializarExplicacion(result) {
            if (window.procesarResultadoPrediccion) {
                window.procesarResultadoPrediccion(result);
            } else {
                console.warn('Sistema de explicación no disponible');
            }
        }        

        // ============= FUNCIONES DE MENSAJES =============
        function showError(message) {
            removeExistingMessages();
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = message;

            const targetContainer = document.getElementById('auth-section').classList.contains('hidden')
                ? document.querySelector('.form-section')
                : document.querySelector('.auth-container');

            targetContainer.appendChild(errorDiv);
            errorDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });

            setTimeout(() => {
                if (errorDiv.parentNode) {
                    errorDiv.parentNode.removeChild(errorDiv);
                }
            }, 5000);
        }


        function showSuccess(message) {
            removeExistingMessages();
            const successDiv = document.createElement('div');
            successDiv.className = 'success-message';
            successDiv.textContent = message;
            
            const targetContainer = document.getElementById('auth-section').classList.contains('hidden')
                ? document.querySelector('.form-section')
                : document.querySelector('.auth-container');
                
            targetContainer.appendChild(successDiv);
            
            setTimeout(() => {
                if (successDiv.parentNode) {
                    successDiv.parentNode.removeChild(successDiv);
                }
            }, 5000);
        }

        function showWarning(message) {
            removeExistingMessages();
            const warningDiv = document.createElement('div');
            warningDiv.className = 'warning-message';
            warningDiv.textContent = message;
            
            const targetContainer = document.getElementById('auth-section').classList.contains('hidden')
                ? document.querySelector('.form-section')
                : document.querySelector('.auth-container');
                
            targetContainer.appendChild(warningDiv);
            
            setTimeout(() => {
                if (warningDiv.parentNode) {
                    warningDiv.parentNode.removeChild(warningDiv);
                }
            }, 6000);
        }

        function removeExistingMessages() {
            const messages = document.querySelectorAll('.error-message, .success-message, .warning-message');
            messages.forEach(msg => {
                if (msg.parentNode) {
                    msg.parentNode.removeChild(msg);
                }
            });
        }

        // ============= MANEJO DE ERRORES GLOBALES =============
        window.addEventListener('error', function(e) {
            console.error('Error global:', e.error);
            showError('Ocurrió un error inesperado. Por favor, recargue la página.');
        });

        // ============= FUNCIONES AUXILIARES =============
        function formatearFecha(fecha) {
            const opciones = { 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric',
                timeZone: 'America/Lima'
            };
            return new Date(fecha).toLocaleDateString('es-PE', opciones);
        }

        function formatearHora(hora) {
            const [horas, minutos] = hora.split(':');
            const horaNum = parseInt(horas);
            const ampm = horaNum >= 12 ? 'PM' : 'AM';
            const hora12 = horaNum % 12 || 12;
            return `${hora12}:${minutos} ${ampm}`;
        }

        function capitalizarPrimeraLetra(str) {
            return str.charAt(0).toUpperCase() + str.slice(1);
        }

        // ============= VALIDACIONES =============
        function validarFormularioCompleto() {
            const vuelosGroups = document.querySelectorAll('.vuelo-group');
            let todosCompletos = true;

            vuelosGroups.forEach((group, index) => {
                const inputs = group.querySelectorAll('input[required], select[required]');
                let grupoCompleto = true;

                inputs.forEach(input => {
                    if (!input.value.trim()) {
                        grupoCompleto = false;
                        input.classList.add('input-error');
                    } else {
                        input.classList.remove('input-error');
                    }
                });

                if (!grupoCompleto) {
                    todosCompletos = false;
                    showError(`Vuelo ${index + 1}: Complete todos los campos requeridos`);
                }
            });

            return todosCompletos;
        }

        function validarFechaFutura(fecha) {
            const fechaSeleccionada = new Date(fecha);
            const hoy = new Date();
            hoy.setHours(0, 0, 0, 0);
            
            return fechaSeleccionada >= hoy;
        }

        function validarHoraRazonable(hora) {
            const [horas, minutos] = hora.split(':').map(Number);
            const horaTotal = horas + (minutos / 60);
            
            // Validar que esté en horario de vuelos comerciales (5:00 AM - 11:00 PM)
            return horaTotal >= 5 && horaTotal <= 23;
        }

        // ============= MANEJO DE DATOS LOCALES =============
        function guardarVueloLocalStorage(vueloData) {
            try {
                const vuelosGuardados = JSON.parse(localStorage.getItem('vuelos_predichos') || '[]');
                vuelosGuardados.push({
                    ...vueloData,
                    timestamp: Date.now()
                });
                localStorage.setItem('vuelos_predichos', JSON.stringify(vuelosGuardados));
            } catch (error) {
                console.warn('No se pudo guardar en localStorage:', error);
            }
        }

        function obtenerVuelosGuardados() {
            try {
                return JSON.parse(localStorage.getItem('vuelos_predichos') || '[]');
            } catch (error) {
                console.warn('No se pudo leer localStorage:', error);
                return [];
            }
        }

        // ============= FUNCIONES DE EXPORTACIÓN =============
        function exportarResultados() {
            const vuelosGuardados = obtenerVuelosGuardados();
            
            if (vuelosGuardados.length === 0) {
                showWarning('No hay predicciones para exportar');
                return;
            }

            const dataStr = JSON.stringify(vuelosGuardados, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            
            const link = document.createElement('a');
            link.href = URL.createObjectURL(dataBlob);
            link.download = `predicciones_vuelos_${new Date().toISOString().split('T')[0]}.json`;
            link.click();
            
            showSuccess('Predicciones exportadas correctamente');
        }

        // ============= FUNCIONES DE NOTIFICACIONES =============
        function solicitarPermisosNotificacion() {
            if ('Notification' in window && Notification.permission === 'default') {
                Notification.requestPermission().then(permission => {
                    if (permission === 'granted') {
                        showSuccess('Notificaciones habilitadas');
                    }
                });
            }
        }

        function enviarNotificacionRetraso(vueloInfo) {
            if ('Notification' in window && Notification.permission === 'granted') {
                const notification = new Notification('⚠️ Alerta de Retraso de Vuelo', {
                    body: `Vuelo a ${vueloInfo.ciudad.toUpperCase()} - ${vueloInfo.fecha} ${vueloInfo.hora}\nProbabilidad de retraso: ${Math.round(vueloInfo.probabilidad)}%`,
                    icon: '/static/icon-192x192.png',
                    tag: 'vuelo-retraso'
                });

                notification.onclick = function() {
                    window.focus();
                    notification.close();
                };

                setTimeout(() => notification.close(), 10000);
            }
        }

        // ============= FUNCIONES DE CONECTIVIDAD =============
        function verificarConexion() {
            return navigator.onLine;
        }

        function manejarConexionPerdida() {
            if (!verificarConexion()) {
                showError('Sin conexión a Internet. Algunas funciones pueden no estar disponibles.');
            }
        }

        // Event listeners para conexión
        window.addEventListener('online', () => {
            showSuccess('Conexión restablecida');
            loadStats();
        });

        window.addEventListener('offline', () => {
            showError('Conexión perdida. Trabajando en modo offline.');
        });

        // ============= FUNCIONES MEJORADAS DE PREDICCIÓN =============
        function procesarResultadoPrediction(result, vueloInfo) {
            // Guardar en localStorage como respaldo
            const vueloCompleto = {
                ...vueloInfo,
                resultado: result,
                timestamp: Date.now()
            };
            guardarVueloLocalStorage(vueloCompleto);

            // Enviar notificación si hay alto riesgo
            if (result.riesgo === 'alto' && result.probabilidad_retraso > 60) {
                enviarNotificacionRetraso({
                    ...vueloInfo,
                    probabilidad: result.probabilidad_retraso
                });
            }

            // Actualizar estadísticas en tiempo real
            actualizarEstadisticasLocales(result);
        }

        function actualizarEstadisticasLocales(result) {
            // Incrementar contador de predicciones
            prediccionesRealizadas++;
            
            // Actualizar contadores si hay riesgo de retraso
            if (result.riesgo === 'alto') {
                retrasos_evitados++;
            }
            
            // Actualizar ahorro estimado
            if (result.ahorro_estimado > 0) {
                ahorroAcumulado += result.ahorro_estimado;
            }
        }

        // ============= FUNCIONES DE LIMPIEZA Y RESET =============
        function limpiarFormulario() {
            const form = document.getElementById('prediction-form');
            if (form) {
                form.reset();
                
                // Limpiar vuelos adicionales
                const vuelosContainer = document.getElementById('vuelos-container');
                const vuelosAdicionales = vuelosContainer.querySelectorAll('.vuelo-group:not(:first-child)');
                vuelosAdicionales.forEach(vuelo => vuelo.remove());
                
                // Reiniciar contadores
                contadorVuelos = 0;
                vuelosPredichos.clear();
                
                // Ocultar resultados
                const resultsSection = document.getElementById('results-section');
                resultsSection.classList.remove('show');
                
                showSuccess('Formulario limpiado');
            }
        }

        function reiniciarEstadisticas() {
            if (confirm('¿Está seguro de que desea reiniciar todas las estadísticas?')) {
                prediccionesRealizadas = 0;
                ahorroAcumulado = 0;
                vuelosPredichos.clear();
                
                // Limpiar localStorage
                localStorage.removeItem('vuelos_predichos');
                
                // Recargar estadísticas
                loadStats();
                
                showSuccess('Estadísticas reiniciadas');
            }
        }

        // ============= MEJORAS EN LA INTERFAZ =============
        function animarElemento(elemento, animacion = 'fadeIn') {
            elemento.classList.add('animate-' + animacion);
            setTimeout(() => {
                elemento.classList.remove('animate-' + animacion);
            }, 500);
        }

        function actualizarTituloPagina(texto) {
            document.title = texto || 'Predictor de Retrasos de Vuelos';
        }

        // ============= FUNCIONES DE MONITOREO =============
        function monitoreRRender() {
            const observer = new MutationObserver(mutations => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList') {
                        // Aplicar animaciones a elementos nuevos
                        mutation.addedNodes.forEach(node => {
                            if (node.nodeType === 1 && node.classList.contains('vuelo-group')) {
                                animarElemento(node, 'slideIn');
                            }
                        });
                    }
                });
            });

            observer.observe(document.getElementById('vuelos-container'), {
                childList: true,
                subtree: true
            });
        }

        // ============= FUNCIONES DE DESARROLLO (solo para testing) =============
        function debugMode() {
            console.log('=== DEBUG MODE ===');
            console.log('Vuelos predichos:', Array.from(vuelosPredichos));
            console.log('Contador vuelos:', contadorVuelos);
            console.log('Usuario actual:', currentUser);
            console.log('Modelo Firebase inicializado:', firebase.apps.length > 0);
            console.log('Predicciones realizadas:', prediccionesRealizadas);
            console.log('Ahorro acumulado:', ahorroAcumulado);
        }

        function configurarSelectsVuelos() {
            const grupos = document.querySelectorAll('.vuelo-group');

            grupos.forEach(grupo => {
                const origen = grupo.querySelector('select[name="origen"]');
                const destino = grupo.querySelector('select[name="ciudad"]');

                // Verificar que ambos selects existan
                if (!origen || !destino) return;

                function sincronizarSelects() {
                    const origenVal = origen.value;
                    const destinoVal = destino.value;

                    // Habilita todas las opciones primero
                    Array.from(destino.options).forEach(op => op.disabled = false);
                    Array.from(origen.options).forEach(op => op.disabled = false);

                    // Si origen ya está seleccionado, deshabilita esa ciudad en el destino
                    if (origenVal) {
                        const opDestino = destino.querySelector(`option[value="${origenVal}"]`);
                        if (opDestino) opDestino.disabled = true;
                    }

                    // Si destino ya está seleccionado, deshabilita esa ciudad en el origen
                    if (destinoVal) {
                        const opOrigen = origen.querySelector(`option[value="${destinoVal}"]`);
                        if (opOrigen) opOrigen.disabled = true;
                    }
                }

                // Remover event listeners existentes para evitar duplicados
                origen.removeEventListener('change', sincronizarSelects);
                destino.removeEventListener('change', sincronizarSelects);

                // Agregar event listeners
                origen.addEventListener('change', sincronizarSelects);
                destino.addEventListener('change', sincronizarSelects);
                sincronizarSelects(); // Inicializa
            });
        }

        async function obtenerPasajerosDelVuelo(numeroVuelo) {
            try {
                const res = await fetch('/tickets');
                const tickets = await res.json();
                return Object.values(tickets).filter(t => t.vuelo?.numero_vuelo === numeroVuelo).length;
            } catch (e) {
                console.error('❌ No se pudo obtener pasajeros:', e);
                return 100; // fallback
            }
        }


        let vuelosProgramados = [];

        async function cargarVuelosProgramados() {
            try {
                const response = await fetch('/vuelos_programados');
                vuelosProgramados = await response.json();

                // Obtener ciudades únicas de origen
                const ciudadesOrigen = [...new Set(vuelosProgramados.map(v => v.origen.toLowerCase()))];

                const origenSelect = document.querySelector('select[name="origen"]');
                origenSelect.innerHTML = '<option value="">Seleccionar ciudad...</option>';
                ciudadesOrigen.forEach(ciudad => {
                    origenSelect.innerHTML += `<option value="${ciudad}">${capitalizarPrimeraLetra(ciudad)}</option>`;
                });

            } catch (error) {
                console.error('❌ Error al cargar vuelos programados:', error);
            }
        }

        document.addEventListener('change', async (e) => {
            if (e.target.name === 'origen' || e.target.name === 'ciudad') {
                const grupo = e.target.closest('.vuelo-group');
                const origen = grupo.querySelector('select[name="origen"]').value;
                const destinoSelect = grupo.querySelector('select[name="ciudad"]');
                const destinoSeleccionado = destinoSelect.value;

                // Filtrar vuelos según origen
                const destinos = vuelosProgramados
                    .filter(v => v.origen === origen)
                    .map(v => v.destino.toLowerCase());

                const destinosUnicos = [...new Set(destinos)];

                // Rellenar destino
                destinoSelect.innerHTML = '<option value="">Seleccionar ciudad...</option>';
                destinosUnicos.forEach(ciudad => {
                    destinoSelect.innerHTML += `<option value="${ciudad}" ${ciudad === destinoSeleccionado ? 'selected' : ''}>${capitalizarPrimeraLetra(ciudad)}</option>`;
                });

                // Si ya hay origen y destino seleccionados, buscar vuelo programado
                const destino = grupo.querySelector('select[name="ciudad"]').value;
                if (origen && destino) {
                    const vuelo = vuelosProgramados.find(v => v.origen === origen && v.destino === destino);

                    if (vuelo) {
                        // Asignar valores a los campos si existen
                        const fechaInput = grupo.querySelector('input[name="fecha"]');
                        const partidaInput = grupo.querySelector('input[name="hora_partida"]');
                        const llegadaInput = grupo.querySelector('input[name="hora_llegada"]');
                        const costoInput = grupo.querySelector('input[name="costo"]');
                        const pasajerosInput = grupo.querySelector('input[name="pasajeros"]');

                        if (fechaInput) fechaInput.value = vuelo.fecha;
                        if (partidaInput) partidaInput.value = vuelo.hora_partida;
                        if (llegadaInput) llegadaInput.value = vuelo.hora_llegada;
                        if (costoInput) costoInput.value = vuelo.precio;

                        // Obtener pasajeros solo si existe input
                        if (pasajerosInput) {
                            const pasajeros = await obtenerPasajerosDelVuelo(vuelo.numero_vuelo);
                            pasajerosInput.value = pasajeros;
                        }
                    }
                }
            }
        });


        // ============= INICIALIZACIÓN CONSOLIDADA =============
        document.addEventListener('DOMContentLoaded', function() {
            // Configurar fecha mínima para todos los inputs de fecha
            const today = new Date().toISOString().split('T')[0];
            const fechaInputs = document.querySelectorAll('input[type="date"]');
            fechaInputs.forEach(input => {
                input.min = today;
            });

            cargarVuelosProgramados();

            // Configurar selects de vuelos
            configurarSelectsVuelos();

            // Inicializar monitoreo
            monitoreRRender();
            
            // Solicitar permisos de notificación
            setTimeout(solicitarPermisosNotificacion, 2000);
            
            // Verificar conexión inicial
            manejarConexionPerdida();
            
            // Configurar shortcuts de teclado
            document.addEventListener('keydown', function(e) {
                // Ctrl + Enter para predecir
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    const form = document.getElementById('prediction-form');
                    if (form) form.dispatchEvent(new Event('submit'));
                }
                
                // Ctrl + N para nuevo vuelo
                if (e.ctrlKey && e.key === 'n') {
                    e.preventDefault();
                    agregarVuelo();
                }
                
                // Ctrl + R para limpiar formulario
                if (e.ctrlKey && e.key === 'r') {
                    e.preventDefault();
                    limpiarFormulario();
                }
            });
            
            console.log('🚀 Aplicación de Predicción de Vuelos inicializada correctamente');
            console.log('📋 Shortcuts disponibles:');
            console.log('   Ctrl + Enter: Realizar predicción');
            console.log('   Ctrl + N: Agregar nuevo vuelo');
            console.log('   Ctrl + R: Limpiar formulario');
        });

        // Hacer disponible para consola
        window.debugMode = debugMode;
        window.limpiarFormulario = limpiarFormulario;
        window.exportarResultados = exportarResultados;
        window.reiniciarEstadisticas = reiniciarEstadisticas;