"""pygame 触屏示例：SDL2 软渲染 + 全比例布局 + 只认手指。

规则（团队约定，别破）：
1. 所有坐标按屏幕宽高百分比算，绝不写死像素 —— 换机型不错位。
2. 不绑实体键：Android 上只有手指。桌面 ESC / 关窗仅用于调试。
3. 帧率锁 60，没事别空转烧电。
4. 任何异常都 traceback 到 stdout，IDE 输出面板能直接看到。

桌面调试：python samples/02_pygame_touch.py   （鼠标点击 = 手指）
手机上：  IDE 里点「运行」，全屏显示，右上角 EXIT 区退出。
"""
import os
import sys
import traceback

try:
    import pygame
except Exception:  # noqa: BLE001
    print("! 缺少 pygame：桌面 `pip install pygame`；"
          "APK 需在 buildozer.spec 的 requirements 里加 pygame（recipe 可用时）")
    raise


def is_android() -> bool:
    return hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ


FD = getattr(pygame, "FINGERDOWN", -1)
FU = getattr(pygame, "FINGERUP", -2)
MD = getattr(pygame, "MOUSEBUTTONDOWN", -3)
MU = getattr(pygame, "MOUSEBUTTONUP", -4)


def main():
    ANDROID = is_android()
    pygame.init()
    if ANDROID:
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        W, H = screen.get_size()
    else:
        W, H = 360, 740
        screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("touch demo")
    clock = pygame.time.Clock()

    def rect(x, y, w, h):  # 百分比 -> 像素
        return pygame.Rect(int(x * W), int(y * H), int(w * W), int(h * H))

    def font(sz):
        return pygame.font.Font(None, max(12, int(sz * H)))

    f_big, f_small = font(0.05), font(0.028)

    R_BTN = rect(0.12, 0.34, 0.76, 0.16)
    R_EXIT = rect(0.70, 0.015, 0.28, 0.055)
    P_BTN = (0.12, 0.34, 0.76, 0.16)
    P_EXIT = (0.70, 0.015, 0.28, 0.055)

    def hit(p, ev):  # ev: (nx, ny) 归一化 0..1
        x, y, w, h = p
        return x <= ev[0] <= x + w and y <= ev[1] <= y + h

    taps = 0
    pressed = False
    marker = None
    running = True

    try:
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type in (FD, MD):
                    if e.type == FD:
                        nx, ny = e.x, e.y
                    else:
                        nx, ny = e.pos[0] / W, e.pos[1] / H
                    marker = (nx, ny)
                    if hit(P_EXIT, (nx, ny)):
                        running = False
                    elif hit(P_BTN, (nx, ny)):
                        pressed = True
                elif e.type in (FU, MU):
                    if pressed:
                        taps += 1
                    pressed = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False  # 仅桌面调试

            screen.fill((14, 16, 22))
            col = (60, 180, 120) if pressed else (36, 44, 58)
            pygame.draw.rect(screen, col, R_BTN, border_radius=int(0.02 * H))
            screen.blit(f_big.render("点我  x%d" % taps, True, (235, 240, 245)),
                        (R_BTN.x + int(0.06 * W), R_BTN.y + int(0.05 * H)))

            pygame.draw.rect(screen, (70, 30, 30), R_EXIT, border_radius=int(0.01 * H))
            screen.blit(f_small.render("EXIT", True, (240, 200, 200)),
                        (R_EXIT.x + int(0.08 * W), R_EXIT.y + int(0.015 * H)))

            if marker:
                pygame.draw.circle(screen, (240, 200, 90),
                                   (int(marker[0] * W), int(marker[1] * H)), int(0.02 * H))

            fps = clock.get_fps()
            screen.blit(f_small.render("FPS %.0f | %dx%d | %s" % (fps, W, H, "android" if ANDROID else "desktop"),
                                       True, (150, 160, 175)), (int(0.03 * W), int(0.92 * H)))
            pygame.display.flip()
            clock.tick(60)  # 锁帧，别空转
    except Exception:  # noqa: BLE001
        traceback.print_exc()
    finally:
        pygame.quit()
    print("taps=%d 退出" % taps)


if __name__ == "__main__":
    main()
