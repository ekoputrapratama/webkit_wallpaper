
/**
 *
 *
 * @class Cubes
 */
class Cubes {
  constructor() {

    this.scene;
    this.camera;
    this.renderer;
    this.innerWidth = window.innerWidth;
    this.innerHeight = window.innerHeight;
    this.container = document.getElementById("canvas");

    this.mainObject = new THREE.Object3D();

    this.xLeftGroup = new THREE.Object3D();
    this.xMiddleGroup = new THREE.Object3D();
    this.xRightGroup = new THREE.Object3D();

    this.whiteCubesPositions = [
      [-1, 1, 1],
      [1, 1, 1],
      [0, 0, 1],
      [-1, -1, 1],
      [1, -1, 1],

      [0, 1, 0],
      [-1, 0, 0],
      [1, 0, 0],
      [0, -1, 0],

      [-1, 1, -1],
      [1, 1, -1],
      [0, 0, -1],
      [-1, -1, -1],
      [1, -1, -1]
    ];

    this.blackCubesPositions = [
      [0, 1, 1],
      [-1, 0, 1],
      [1, 0, 1],
      [0, -1, 1],

      [-1, 1, 0],
      [1, 1, 0],
      [0, 0, 0],
      [-1, -1, 0],
      [1, -1, 0],

      [0, 1, -1],
      [-1, 0, -1],
      [1, 0, -1],
      [0, -1, -1]
    ];

    this.cubeSize = 4;

    this.init();
  }

  init() {
    this.scene = new THREE.Scene();

    this.camera = new THREE.OrthographicCamera(
      this.innerWidth / -2,
      this.innerWidth / 2,
      this.innerHeight / 2,
      this.innerHeight / -2,
      1,
      100
    );
    this.camera.position.set(0, 0, 50);
    this.camera.zoom = 15;
    this.camera.lookAt(0, 0, 0);
    this.scene.add(this.camera);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setSize(this.innerWidth, this.innerHeight);
    this.renderer.setClearColor(0x292929);
    this.renderer.clear();
    this.container.appendChild(this.renderer.domElement);

    this.resize();
    window.addEventListener("resize", this.resize.bind(this), false);

    this.createScene();
  }

  createScene() {
    this.buildCubes(this.cubeSize);

    this.mainObject.add(this.xLeftGroup);
    this.mainObject.add(this.xMiddleGroup);
    this.mainObject.add(this.xRightGroup);

    this.scene.add(this.mainObject);

    this.resetPositions();

    this.animate();
  }

  resetPositions() {
    this.mainObject.rotation.x = (Math.PI / 180) * 35;
    this.mainObject.rotation.y = (Math.PI / 180) * 45;
    this.mainObject.rotation.z = 0;

    this.animateCubes();
  }

  animateCubes() {
    TweenMax.to(this.xMiddleGroup.rotation, 0.5, {
      x: this.xMiddleGroup.rotation.x + (Math.PI / 180) * 90,
      ease: Power1.easeInOut
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: -this.cubeSize * 0.5,
      ease: Power1.easeInOut
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: this.cubeSize * 0.5,
      ease: Power1.easeInOut
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: 0,
      delay: 0.25,
      ease: Power1.easeInOut
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: 0,
      delay: 0.25,
      ease: Power1.easeInOut
    });

    TweenMax.set(this.mainObject.rotation, {
      x: (Math.PI / 180) * 35,
      y: (Math.PI / 180) * 45,
      z: (Math.PI / 180) * 90,
      delay: 0.5
    });

    TweenMax.to(this.xMiddleGroup.rotation, 0.5, {
      x: this.xMiddleGroup.rotation.x + Math.PI / 180,
      ease: Power1.easeInOut,
      delay: 0.5
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: -this.cubeSize * 0.5,
      ease: Power1.easeInOut,
      delay: 0.5
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: this.cubeSize * 0.5,
      ease: Power1.easeInOut,
      delay: 0.5
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: 0,
      ease: Power1.easeInOut,
      delay: 0.75
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: 0,
      ease: Power1.easeInOut,
      delay: 0.75
    });

    TweenMax.set(this.mainObject.rotation, {
      x: (Math.PI / 180) * 35,
      y: (Math.PI / 180) * 135,
      z: (Math.PI / 180) * 0,
      ease: Power1.easeInOut,
      delay: 1
    });

    TweenMax.to(this.xMiddleGroup.rotation, 0.5, {
      x: this.xMiddleGroup.rotation.x + (Math.PI / 180) * 90,
      ease: Power1.easeInOut,
      delay: 1
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: -this.cubeSize * 0.5,
      ease: Power1.easeInOut,
      delay: 1
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: this.cubeSize * 0.5,
      ease: Power1.easeInOut,
      delay: 1
    });
    TweenMax.to(this.xLeftGroup.position, 0.25, {
      x: 0,
      ease: Power1.easeInOut,
      delay: 1.25
    });
    TweenMax.to(this.xRightGroup.position, 0.25, {
      x: 0,
      ease: Power1.easeInOut,
      delay: 1.25,
      onComplete: this.resetPositions.bind(this)
    });
  }

  buildCubes(cubeSize) {
    const cubeGeometry = new THREE.CubeGeometry(
      cubeSize,
      cubeSize,
      cubeSize
    );
    const whiteCubeMaterial = new THREE.MeshBasicMaterial({
      color: 0xdfdfc3
    });
    const blackCubeMaterial = new THREE.MeshBasicMaterial({
      color: 0x292929
    });

    for (let i = 0; i < 14; i++) {
      let cube = new THREE.Mesh(cubeGeometry, whiteCubeMaterial);
      cube.position.x = this.whiteCubesPositions[i][0] * cubeSize;
      cube.position.y = this.whiteCubesPositions[i][1] * cubeSize;
      cube.position.z = this.whiteCubesPositions[i][2] * cubeSize;

      if (cube.position.x == -1 * cubeSize) {
        this.xLeftGroup.add(cube);
      }
      if (cube.position.x == 0 * cubeSize) {
        this.xMiddleGroup.add(cube);
      }
      if (cube.position.x == 1 * cubeSize) {
        this.xRightGroup.add(cube);
      }
    }

    for (let i = 0; i < 13; i++) {
      let cube = new THREE.Mesh(cubeGeometry, blackCubeMaterial);
      cube.position.x = this.blackCubesPositions[i][0] * cubeSize;
      cube.position.y = this.blackCubesPositions[i][1] * cubeSize;
      cube.position.z = this.blackCubesPositions[i][2] * cubeSize;

      if (cube.position.x == -1 * cubeSize) {
        this.xLeftGroup.add(cube);
      }
      if (cube.position.x == 0 * cubeSize) {
        this.xMiddleGroup.add(cube);
      }
      if (cube.position.x == 1 * cubeSize) {
        this.xRightGroup.add(cube);
      }
    }
  }

  animate() {
    this.render();
  }

  render() {
    window.requestAnimationFrame(this.animate.bind(this));

    this.renderer.render(this.scene, this.camera);
  }

  resize() {
    this.innerWidth = window.innerWidth;
    this.innerHeight = window.innerHeight;

    this.camera.aspect = this.innerWidth / this.innerHeight;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(this.innerWidth, this.innerHeight);
  }
}

let experience = new Cubes();
